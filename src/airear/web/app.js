'use strict';
const $ = id => document.getElementById(id);
let pc = null, token = null, peerId = null, context = null, gain = null, source = null;
let wanted = false, retry = null, connectTimer = null, attempts = 0, generation = 0;
const status = text => { $('status').textContent = text; };
$('transport').textContent = location.protocol === 'https:' ? 'HTTPS 시그널링을 사용하고 있습니다.' : 'HTTP 연결: PIN과 인증정보가 LAN에서 노출될 수 있습니다. 신뢰하는 Wi-Fi에서 사용하고 앱에서 HTTPS를 설정하세요.';
async function api(path, options = {}, bearer = token) {
  const response = await fetch(path, { ...options, headers: {'Content-Type':'application/json', ...(bearer ? {'Authorization': `Bearer ${bearer}`} : {}), ...options.headers}, signal: AbortSignal.timeout(20000) });
  if (!response.ok) { if(response.status === 401 && token === bearer) token = null; throw new Error(await response.text()); }
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
  if (++attempts > 6) { wanted = false; status('재연결하지 못했습니다. PIN을 확인하고 듣기 버튼을 다시 눌러주세요.'); $('connect').disabled = false; $('stop').disabled = true; return; }
  status(`네트워크 연결이 끊겼습니다. 재연결 시도 ${attempts}/6`);
  retry = setTimeout(() => { retry = null; connect(false); }, Math.min(1000 * 2 ** attempts, 15000));
}
async function connect(gesture) {
  const current = ++generation;
  try {
    if (!window.RTCPeerConnection) throw new Error('이 브라우저에서 WebRTC를 사용할 수 없습니다. 최신 Safari를 사용하세요.');
    wanted = true; $('connect').disabled = true; $('stop').disabled = false;
    if (gesture) {
      attempts = 0;
      context ||= new (window.AudioContext || window.webkitAudioContext)();
      context.onstatechange = () => {
        if (wanted && ['suspended','interrupted'].includes(context.state)) {
          $('connect').disabled = false;
          status('iOS가 재생을 일시 중지했습니다. 듣기 버튼을 다시 눌러주세요.');
        }
      };
      // Resume immediately inside the explicit click, before network awaits.
      await context.resume();
    }
    status('인증 및 오디오 연결 중…');
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
      try { await context.resume(); if (pc !== connection || current !== generation) return; if(context.state !== 'running') throw new Error(); status('오디오 수신 중 · 수신 음량은 iPhone 버튼으로도 조절할 수 있습니다.'); }
      catch { if (pc !== connection || current !== generation) return; wanted = false; teardown(); $('connect').disabled = false; $('stop').disabled = true; status('Safari가 재생을 중지했습니다. 듣기 버튼을 다시 눌러주세요.'); }
    };
    connection.onconnectionstatechange = () => {
      if (pc !== connection) return;
      if(connection.connectionState === 'connected') { clearTimeout(connectTimer); connectTimer = null; attempts = 0; status('연결됨 · 오디오 수신 중'); }
      if(['failed','disconnected'].includes(connection.connectionState)) reconnect();
    };
    await connection.setLocalDescription(await connection.createOffer());
    if (connection.iceGatheringState !== 'complete') await new Promise((resolve,reject)=>{
      const timer = setTimeout(()=>reject(new Error('네트워크 후보 수집 시간 초과')),10000);
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
    wanted = false; $('connect').disabled = false; $('stop').disabled = true; status(error.message || '연결하지 못했습니다.');
  }
}
$('connect').addEventListener('click',()=>{teardown();connect(true);});
$('stop').addEventListener('click',()=>{wanted=false;++generation;teardown();$('connect').disabled=false;$('stop').disabled=true;status('연결이 해제되었습니다.');});
$('volume').addEventListener('input',()=>{const value=Number($('volume').value);if(gain)gain.gain.value=value/100;$('volumeLabel').textContent=`${value}%`;});
window.addEventListener('online',()=>{if(wanted)reconnect();});
window.addEventListener('pagehide',()=>{wanted=false;++generation;teardown();});

window.addEventListener('pageshow',()=>{if(!wanted){$('connect').disabled=false;$('stop').disabled=true;}});
