'use strict';

const api = window.airEar;
const $ = selector => document.querySelector(selector);
const shell = $('.shell');
let appState = null;
let strings = {};
let server = { running: false, clients: [], addresses: [] };
let signalSocket = null;
let rawStream = null;
let outputStream = null;
let audioContext = null;
let analyser = null;
let meterFrame = 0;
const peers = new Map();
let updateState = { state: 'idle' };
let languageCheck = null;

function getString(key) {
  return key.split('.').reduce((value, part) => value && value[part], strings) || key;
}

async function applyLanguage(language) {
  try {
    strings = await api.readLanguage(language);
    document.documentElement.lang = language;
    document.querySelectorAll('[data-i18n]').forEach(element => {
      element.textContent = getString(element.dataset.i18n);
    });
  } catch (error) {
    console.error('Language file could not be loaded', error);
  }
}

function setTheme(theme) {
  const dark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  shell.classList.toggle('dark', dark);
}

function showView(id) {
  document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === id));
  document.querySelectorAll('.nav-item').forEach(button => button.classList.toggle('active', button.dataset.target === id));
}

function setServerStatus(running) {
  $('#serverState').textContent = getString(running ? 'status.running' : 'status.stopped');
  $('#serverBadge').textContent = getString(running ? 'status.running' : 'status.stopped');
  $('#serverBadge').classList.toggle('muted', !running);
  $('#serverDot').classList.toggle('live', running);
  $('#sidebarDot').classList.toggle('live', running);
  $('#sidebarStatus').textContent = getString(running ? 'status.running' : 'status.stopped');
  $('#serverButton').querySelector('span').textContent = getString(running ? 'button.stopServer' : 'button.startServer');
  $('#serverButton').disabled = !!appState?.busy;
  $('#port').disabled = running;
}

function chosenAddress() {
  const text = $('#lanAddress').value.trim();
  const parts = text.split('.');
  const octets = parts.map(value => /^\d{1,3}$/.test(value) ? Number(value) : -1);
  const valid = octets.length === 4 && octets.every(value => value >= 0 && value <= 255);
  const privateAddress = valid && (octets[0] === 10 || (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31) || (octets[0] === 192 && octets[1] === 168));
  return privateAddress ? text : (server.addresses[0] || '');
}

async function refreshConnection() {
  if (!server.running) {
    $('#phoneUrl').textContent = getString('phone.waiting');
    $('#pinValue').textContent = '••••••••';
    $('#qr').removeAttribute('src');
    $('#connectionSummary').textContent = getString('phone.waiting');
    return;
  }
  const host = chosenAddress();
  if (!host) {
    $('#phoneUrl').textContent = getString('phone.noAddress');
    $('#qr').removeAttribute('src');
    return;
  }
  const url = `http://${host}:${server.port}/`;
  $('#phoneUrl').textContent = url;
  $('#pinValue').textContent = server.pin || '••••••••';
  $('#connectionSummary').textContent = `${url} · ${getString('phone.pin')}: ${server.pin || '••••••••'}`;
  try { $('#qr').src = await api.createQr(url); } catch { $('#qr').removeAttribute('src'); }
}

function renderClients(clients = server.clients || []) {
  const root = $('#clients');
  $('#clientCount').textContent = String(clients.length);
  root.replaceChildren();
  if (!clients.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = getString('clients.empty');
    root.append(empty);
    return;
  }
  for (const client of clients) {
    const row = document.createElement('div');
    row.className = 'client';
    const address = document.createElement('span');
    address.textContent = client.address || getString('phone.receiver');
    const status = document.createElement('span');
    status.textContent = peers.get(client.id)?.state || getString('clients.connected');
    const disconnect = document.createElement('button');
    disconnect.textContent = getString('button.disconnect');
    disconnect.addEventListener('click', () => sendSignal({ type: 'close-peer', peerId: client.id }));
    row.append(address, status, disconnect);
    root.append(row);
  }
}

function setAudioStatus(active, message) {
  $('#audioBadge').textContent = message || getString(active ? 'audio.live' : 'audio.idle');
  $('#audioBadge').classList.toggle('muted', !active);
  $('#broadcastButton').disabled = active;
  $('#stopBroadcastButton').disabled = !active;
  $('#broadcastButton').querySelector('span').textContent = getString(active ? 'audio.live' : 'button.startBroadcast');
}

function sendSignal(value) {
  if (signalSocket?.readyState === WebSocket.OPEN) signalSocket.send(JSON.stringify(value));
}

async function startServer() {
  try {
    const port = Number($('#port').value) || 8765;
    await api.saveSettings({ port, autoStart: $('#autoStart').checked });
    const state = await api.startServer();
    server = state;
    if (!$('#lanAddress').value.trim() || !state.addresses.includes($('#lanAddress').value.trim())) {
      $('#lanAddress').value = state.addresses[0] || '';
    }
    setServerStatus(true);
    await refreshConnection();
    renderClients(state.clients);
  } catch (error) {
    alert(`${getString('error.serverStart')}\n${error.message || error}`);
  }
}

async function stopServer() {
  stopAudio();
  try {
    server = await api.stopServer();
    setServerStatus(false);
    await refreshConnection();
    renderClients([]);
  } catch (error) { alert(`${getString('error.serverStop')}\n${error.message || error}`); }
}

async function startAudio() {
  if (!server.running) await startServer();
  if (!server.running) return;
  try {
    rawStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
    for (const track of rawStream.getVideoTracks()) track.stop();
    if (!rawStream.getAudioTracks().length) throw new Error(getString('error.noAudioTrack'));
    audioContext = new AudioContext({ latencyHint: 'interactive' });
    const source = audioContext.createMediaStreamSource(rawStream);
    const gain = audioContext.createGain();
    const limiter = audioContext.createDynamicsCompressor();
    limiter.threshold.value = -2;
    limiter.knee.value = 3;
    limiter.ratio.value = 12;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.12;
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(gain).connect(limiter).connect(analyser);
    const destination = audioContext.createMediaStreamDestination();
    analyser.connect(destination);
    outputStream = destination.stream;
    gainNode = gain;
    syncGain();
    rawStream.getAudioTracks()[0].addEventListener('ended', stopAudio, { once: true });
    await audioContext.resume();
    openDesktopSocket();
    startMeter();
    setAudioStatus(true);
  } catch (error) {
    stopAudio();
    alert(`${getString('error.capture')}\n${error.message || error}`);
  }
}

let gainNode = null;

function openDesktopSocket() {
  api.getDesktopSession().then(({ port, token }) => {
    signalSocket = new WebSocket(`ws://127.0.0.1:${port}/signal`);
    signalSocket.onopen = () => signalSocket.send(JSON.stringify({ type: 'desktop', token }));
    signalSocket.onmessage = event => handleDesktopMessage(JSON.parse(event.data));
    signalSocket.onerror = () => { $('#audioBadge').textContent = getString('error.signaling'); };
    signalSocket.onclose = () => {
      if (outputStream) stopAudio();
    };
  }).catch(error => alert(`${getString('error.signaling')}\n${error.message || error}`));
}

async function handleDesktopMessage(message) {
  if (message.type === 'peer-joined') return;
  if (message.type === 'offer') return acceptOffer(message.peerId, message.sdp);
  if (message.type === 'ice') {
    const peer = peers.get(message.peerId);
    if (peer) {
      if (peer.pc.remoteDescription) peer.pc.addIceCandidate(message.candidate).catch(() => {});
      else peer.pending.push(message.candidate);
    }
  } else if (message.type === 'close-peer') {
    closePeer(message.peerId);
  }
}

async function acceptOffer(peerId, sdp) {
  closePeer(peerId, false);
  const pc = new RTCPeerConnection({ iceServers: [], bundlePolicy: 'max-bundle' });
  const peer = { pc, pending: [], state: 'connecting' };
  peers.set(peerId, peer);
  pc.addTrack(outputStream.getAudioTracks()[0], outputStream);
  pc.onicecandidate = event => { if (event.candidate) sendSignal({ type: 'ice', peerId, candidate: event.candidate }); };
  pc.onconnectionstatechange = () => {
    peer.state = pc.connectionState;
    renderClients();
    sendSignal({ type: 'peer-state', peerId, state: peer.state });
    if (['failed', 'closed'].includes(pc.connectionState)) closePeer(peerId);
  };
  try {
    await pc.setRemoteDescription({ type: 'offer', sdp });
    for (const candidate of peer.pending.splice(0)) await pc.addIceCandidate(candidate).catch(() => {});
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    sendSignal({ type: 'answer', peerId, sdp: pc.localDescription.sdp });
  } catch (error) {
    sendSignal({ type: 'close-peer', peerId });
    closePeer(peerId);
    console.error('WebRTC negotiation failed', error);
  }
}

function closePeer(peerId, notify = false) {
  const peer = peers.get(peerId);
  if (!peer) return;
  peers.delete(peerId);
  try { peer.pc.close(); } catch { /* already closed */ }
  if (notify) sendSignal({ type: 'close-peer', peerId });
  renderClients();
}

function startMeter() {
  if (!analyser) return;
  const data = new Uint8Array(analyser.frequencyBinCount);
  const draw = () => {
    if (!analyser) return;
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (const sample of data) { const delta = (sample - 128) / 128; sum += delta * delta; }
    const level = Math.min(100, Math.round(Math.sqrt(sum / data.length) * 260));
    $('#meterFill').style.width = `${level}%`;
    meterFrame = requestAnimationFrame(draw);
  };
  draw();
}

function syncGain() {
  if (!gainNode) return;
  gainNode.gain.value = $('#mute').checked ? 0 : Number($('#gain').value) / 100;
  $('#gainText').textContent = `${$('#gain').value}%`;
}

function stopAudio() {
  cancelAnimationFrame(meterFrame);
  for (const id of [...peers.keys()]) closePeer(id);
  const socket = signalSocket;
  signalSocket = null;
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'broadcast-stopped');
  for (const track of rawStream?.getTracks() || []) track.stop();
  rawStream = null;
  outputStream = null;
  analyser = null;
  gainNode = null;
  if (audioContext) audioContext.close().catch(() => {});
  audioContext = null;
  $('#meterFill').style.width = '0';
  setAudioStatus(false);
}

function renderDiagnostics() {
  $('#diagnosticText').textContent = JSON.stringify({ version: appState?.version, platform: navigator.platform, server: { running: server.running, port: server.port, localAddresses: server.addresses }, connectedPhones: (server.clients || []).length, streaming: !!outputStream }, null, 2);
}

function setUpdateButton(state) {
  updateState = state;
  const button = $('#updateButton');
  if (state.state === 'available') button.textContent = `${getString('update.available')} ${state.version}`;
  else if (state.state === 'downloading') button.textContent = `${getString('update.downloading')} ${state.percent}%`;
  else if (state.state === 'downloaded') button.textContent = getString('update.install');
  else if (state.state === 'none') button.textContent = getString('update.none');
  else button.textContent = getString('button.checkUpdates');
  button.disabled = state.state === 'downloading';
}

async function updateButtonClick() {
  if (updateState.state === 'available') {
    setUpdateButton({ state: 'downloading', percent: 0 });
    await api.downloadUpdate();
  } else if (updateState.state === 'downloaded') {
    await api.installUpdate();
  } else {
    setUpdateButton({ state: 'checking' });
    const result = await api.checkUpdates();
    if (!result.supported) setUpdateButton({ state: 'manual' });
    else if (result.update) setUpdateButton({ state: 'available', version: result.version });
    else setUpdateButton({ state: 'none' });
  }
}

async function initialize() {
  appState = await api.getState();
  $('#version').textContent = `v${appState.version}`;
  $('#footerVersion').textContent = `AirEar ${appState.version}`;
  $('#port').value = appState.settings.port;
  $('#autoStart').checked = appState.settings.autoStart;
  $('#gain').value = Math.round(appState.settings.gain * 100);
  $('#mute').checked = !!appState.settings.muted;
  $('#theme').value = appState.settings.theme || 'system';
  $('#updates').checked = appState.settings.checkUpdates !== false;
  $('#language').value = appState.settings.language || 'ko';
  await applyLanguage($('#language').value);
  setTheme($('#theme').value);
  server = appState.server;
  setServerStatus(server.running);
  if (server.running) {
    $('#lanAddress').value = server.addresses[0] || '';
    await refreshConnection();
  } else {
    const found = await api.getState();
    server.addresses = found.server.addresses || [];
    $('#lanAddress').value = server.addresses[0] || '';
  }
  renderClients(server.clients || []);
  renderDiagnostics();
}

document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => showView(button.dataset.target)));
$('#settingsButton').addEventListener('click', () => showView('settings'));
$('#serverButton').addEventListener('click', () => server.running ? stopServer() : startServer());
$('#broadcastButton').addEventListener('click', startAudio);
$('#stopBroadcastButton').addEventListener('click', stopAudio);
$('#gain').addEventListener('input', () => { syncGain(); api.saveSettings({ gain: Number($('#gain').value) / 100 }); });
$('#mute').addEventListener('change', () => { syncGain(); api.saveSettings({ muted: $('#mute').checked }); });
$('#lanAddress').addEventListener('input', refreshConnection);
$('#autoStart').addEventListener('change', () => api.saveSettings({ autoStart: $('#autoStart').checked }));
$('#theme').addEventListener('change', () => { setTheme($('#theme').value); api.saveSettings({ theme: $('#theme').value }); });
$('#updates').addEventListener('change', () => api.saveSettings({ checkUpdates: $('#updates').checked }));
$('#language').addEventListener('change', async () => { await api.saveSettings({ language: $('#language').value }); await applyLanguage($('#language').value); setServerStatus(server.running); renderClients(); setUpdateButton(updateState); });
$('#copyUrl').addEventListener('click', () => api.copy($('#phoneUrl').textContent));
$('#openLog').addEventListener('click', () => api.openLog());
$('#copyDiagnostics').addEventListener('click', () => { renderDiagnostics(); api.copy($('#diagnosticText').textContent); });
$('#updateButton').addEventListener('click', updateButtonClick);
api.onServerState(state => { server = state; setServerStatus(state.running); refreshConnection(); renderClients(state.clients); renderDiagnostics(); });
api.onUpdateState(setUpdateButton);
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if ($('#theme').value === 'system') setTheme('system'); });
initialize().then(() => {
  languageCheck = setInterval(() => applyLanguage($('#language').value), 2500);
  void languageCheck;
});
