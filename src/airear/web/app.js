'use strict';
const $ = id => document.getElementById(id);
let language = navigator.language.startsWith('ko') ? 'ko' : 'en';
try { language=localStorage.getItem('airear.language') || language; } catch { /* Storage may be blocked by browser privacy settings. */ }
let messages = {}, defaultMessages = {};
function t(key, args={}) {
  return String(messages[key] ?? defaultMessages[key] ?? key).replace(/\{(\w+)\}/g, (_, name)=>String(args[name] ?? `{${name}}`));
}
async function loadLanguage() {
  try {
    const response=await fetch(`/languages/${encodeURIComponent(language)}.json`, {cache:'no-store'});
    if(!response.ok)throw new Error();
    messages=(await response.json()).web || {};
    document.documentElement.lang=language;
    document.querySelectorAll('[data-i18n]').forEach(node=>node.textContent=t(node.dataset.i18n));
    $('pin').placeholder=t('pin_placeholder');
    $('language').setAttribute('aria-label',t('language'));
    $('transport').textContent=t(location.protocol==='https:' ? 'https' : 'http');
    if(statusKey)$('status').textContent=t(statusKey,statusArgs);
  } catch { /* Keep last valid pack while a file is being edited. */ }
}
async function initializeLanguages() {
  try {
    const response=await fetch('/languages/en.json',{cache:'no-store'});
    defaultMessages=(await response.json()).web || {};
    const available=await (await fetch('/languages',{cache:'no-store'})).json();
    $('language').replaceChildren(...available.map(item=>{const option=document.createElement('option');option.value=item.code;option.textContent=item.name;return option;}));
    if(!available.some(item=>item.code===language))language='en';
    $('language').value=language;
  } catch { language='en'; }
  await loadLanguage();
}
$('language').addEventListener('change',()=>{language=$('language').value;try { localStorage.setItem('airear.language',language); } catch { /* Session-only selection still works. */ } loadLanguage();});
initializeLanguages();
setInterval(loadLanguage,2000);

let pc = null, token = null, peerId = null, context = null, gain = null, source = null;
let wanted = false, retry = null, connectTimer = null, attempts = 0, generation = 0;
let statusKey='waiting', statusArgs={};
const status = (key, args={}) => {
  statusArgs=args;
  statusKey=Object.hasOwn(messages,key)||Object.hasOwn(defaultMessages,key) ? key : Object.keys(messages).find(candidate=>t(candidate,args)===key);
  $('status').textContent=statusKey ? t(statusKey,args) : key;
};
async function api(path, options = {}, bearer = token) {
  const response = await fetch(path, { ...options, headers: {'Content-Type':'application/json', 'X-AirEar-Language':language, ...(bearer ? {'Authorization': `Bearer ${bearer}`} : {}), ...options.headers}, signal: AbortSignal.timeout(20000) });
  if (!response.ok) { if(response.status === 401 && token === bearer) token = null; const message=await response.text(); const error=new Error(message); error.localized=true; throw error; }
  return response.status === 204 ? null : response.json();
}
function teardown() {
  ++generation; // Invalidate pending authentication, offers and playback promises.
  clearTimeout(retry); retry = null;
  clearTimeout(connectTimer); connectTimer = null;
  if (pc) { pc.onconnectionstatechange = null; pc.close(); pc = null; }
  if (source) { source.disconnect(); source = null; }
  if (gain) { gain.disconnect(); gain = null; }
  $('audio').srcObject = null;
  if (peerId) { const id = peerId; peerId = null; api(`/api/peers/${id}`, {method:'DELETE'}).catch(()=>{}); }
}
function reconnect() {
  if (!wanted || retry) return;
  teardown();
  if (++attempts > 6) { wanted = false; status('retry_failed'); $('connect').disabled = false; $('stop').disabled = true; return; }
  status('retry', {attempts});
  retry = setTimeout(() => { retry = null; connect(false); }, Math.min(1000 * 2 ** attempts, 15000));
}
async function connect(gesture) {
  const current = ++generation;
  try {
    if (!window.RTCPeerConnection) throw new Error(t('unsupported'));
    wanted = true; $('connect').disabled = true; $('stop').disabled = false;
    if (gesture) {
      attempts = 0;
      context ||= new (window.AudioContext || window.webkitAudioContext)();
      context.onstatechange = () => {
        if (wanted && ['suspended','interrupted'].includes(context.state)) {
          $('connect').disabled = false;
          status('paused');
        }
      };
      // Resume immediately inside the explicit click, before network awaits.
      await context.resume();
    }
    status('connecting');
    if (!token) {
      const result = await api('/api/auth', {method:'POST',body:JSON.stringify({pin:$('pin').value.trim()})});
      if (!wanted || current !== generation) return;
      token = result.token;
    }
    if (!wanted || current !== generation) return;
    const connection = new RTCPeerConnection({iceServers:[]}); pc = connection;
    connection.addTransceiver('audio',{direction:'recvonly'});
    connection.ontrack = async event => {
      if (pc !== connection || current !== generation) return;
      const stream = new MediaStream([event.track]);
      $('audio').srcObject = stream;
      // Web Audio gain is used because iOS ignores HTMLMediaElement.volume.
      source = context.createMediaStreamSource(stream); gain = context.createGain();
      gain.gain.value = Number($('volume').value) / 100; source.connect(gain); gain.connect(context.destination);
      try { await context.resume(); if (pc !== connection || current !== generation) return; if(context.state !== 'running') throw new Error(); status('receiving'); }
      catch { if (pc !== connection || current !== generation) return; wanted = false; teardown(); $('connect').disabled = false; $('stop').disabled = true; status('playback_stopped'); }
    };
    connection.onconnectionstatechange = () => {
      if (pc !== connection) return;
      if(connection.connectionState === 'connected') { clearTimeout(connectTimer); connectTimer = null; attempts = 0; status('connected'); }
      if(['failed','disconnected'].includes(connection.connectionState)) reconnect();
    };
    await connection.setLocalDescription(await connection.createOffer());
    if (connection.iceGatheringState !== 'complete') await new Promise((resolve,reject)=>{
      const timer = setTimeout(()=>reject(new Error(t('ice_timeout'))),10000);
      connection.addEventListener('icegatheringstatechange',()=>{if(connection.iceGatheringState==='complete'){clearTimeout(timer);resolve();}});
    });
    if (!wanted || current !== generation) return;
    const offerToken = token;
    const answer = await api('/api/offer',{method:'POST',body:JSON.stringify(connection.localDescription)}, offerToken);
    if (!wanted || current !== generation) { await api(`/api/peers/${answer.id}`,{method:'DELETE'}, offerToken).catch(()=>{}); return; }
    peerId = answer.id;
    await connection.setRemoteDescription({type:answer.type,sdp:answer.sdp});
    if (pc === connection && current === generation && connection.connectionState !== 'connected') {
      connectTimer = setTimeout(()=>{
        connectTimer = null;
        if (pc === connection && wanted && connection.connectionState !== 'connected') reconnect();
      }, 15000);
    }
  } catch(error) {
    if (current !== generation) return;
    teardown();
    if(wanted && !gesture && token) { reconnect(); return; }
    wanted = false; $('connect').disabled = false; $('stop').disabled = true; status(error.message || 'failed');
  }
}
$('connect').addEventListener('click',()=>{teardown();connect(true);});
$('stop').addEventListener('click',()=>{wanted=false;++generation;teardown();$('connect').disabled=false;$('stop').disabled=true;status('disconnected');});
$('volume').addEventListener('input',()=>{const value=Number($('volume').value);if(gain)gain.gain.value=value/100;$('volumeLabel').textContent=`${value}%`;});
window.addEventListener('online',()=>{if(wanted)reconnect();});
window.addEventListener('pagehide',()=>{wanted=false;++generation;teardown();});

window.addEventListener('pageshow',()=>{if(!wanted){$('connect').disabled=false;$('stop').disabled=true;}});
