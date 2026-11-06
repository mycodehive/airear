'use strict';

const api = window.airEar;
const $ = selector => document.querySelector(selector);
const shell = $('.shell');
let appState = null;
let strings = {};
let server = { running: false, clients: [], addresses: [] };
let signalSocket = null;
let outputStream = null;
let audioContext = null;
let audioWorkletNode = null;
let analyser = null;
let meterFrame = 0;
let outputDevices = [];
const peers = new Map();
let updateState = { state: 'idle' };
let languageCheck = null;
let qrGeneration = 0;
let broadcastStarting = false;

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

function clearQrImages() {
  qrGeneration++;
  document.querySelectorAll('[data-connection-qr]').forEach(image => image.removeAttribute('src'));
}

async function showQr(url) {
  const generation = ++qrGeneration;
  try {
    const imageUrl = await api.createQr(url);
    if (generation !== qrGeneration) return;
    document.querySelectorAll('[data-connection-qr]').forEach(image => { image.src = imageUrl; });
  } catch (error) {
    if (generation !== qrGeneration) return;
    clearQrImages();
    console.error('Could not create connection QR code', error);
  }
}

async function refreshConnection() {
  if (!server.running) {
    $('#phoneUrl').textContent = getString('phone.waiting');
    $('#pinValue').textContent = '••••••••';
    $('#connectionPin').textContent = '••••••••';
    clearQrImages();
    $('#connectionSummary').textContent = getString('phone.waiting');
    return;
  }
  if (!outputStream) { clearQrImages(); }
  const host = chosenAddress();
  if (!host) {
    $('#phoneUrl').textContent = getString('phone.noAddress');
    $('#connectionPin').textContent = '••••••••';
    clearQrImages();
    return;
  }
  const url = `http://${host}:${server.port}/`;
  $('#phoneUrl').textContent = url;
  $('#pinValue').textContent = server.pin || '••••••••';
  $('#connectionPin').textContent = server.pin || '••••••••';
  $('#connectionSummary').textContent = `${url} · ${getString('phone.pin')}: ${server.pin || '••••••••'}`;
  if (outputStream) await showQr(url);
}

async function refreshLanAddress() {
  const button = $('#refreshAddress');
  button.disabled = true;
  $('#lanAddress').value = '';
  server.addresses = [];
  clearQrImages();
  try {
    server.addresses = await api.refreshLanAddresses();
    $('#lanAddress').value = server.addresses[0] || '';
    await refreshConnection();
  } catch (error) {
    $('#phoneUrl').textContent = `${getString('error.addressRefresh')} ${error.message || error}`;
  } finally {
    button.disabled = false;
  }
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

function cableDevice() {
  return outputDevices.find(device => /cable\s*input/i.test(device.name) && /vb\s*-?\s*audio/i.test(device.name))
    || outputDevices.find(device => /cable\s*input/i.test(device.name));
}

async function refreshAudioDevices() {
  const previous = $('#outputDevice').value || appState?.settings.outputDeviceId;
  $('#refreshDevices').disabled = true;
  try {
    outputDevices = await api.listAudioDevices();
    const select = $('#outputDevice');
    select.replaceChildren();
    for (const device of outputDevices) {
      const option = document.createElement('option');
      option.value = device.id;
      option.textContent = `${device.name}${device.isDefault ? ` · ${getString('audio.defaultDevice')}` : ''}`;
      select.append(option);
    }
    if (!outputDevices.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = getString('audio.noDevices');
      select.append(option);
      $('#audioDeviceHelp').textContent = getString('audio.noDevices');
      return;
    }
    const cable = cableDevice();
    const saved = outputDevices.find(device => device.id === previous);
    const preferred = cable || saved || outputDevices.find(device => device.isDefault) || outputDevices[0];
    select.value = preferred.id;
    $('#audioDeviceHelp').textContent = cable ? getString('audio.cable') : getString('audio.cableMissing');
    await api.saveSettings({ outputDeviceId: preferred.id });
  } catch (error) {
    console.error('Could not enumerate WASAPI output devices', error);
    outputDevices = [];
    $('#audioDeviceHelp').textContent = `${getString('audio.deviceError')} ${error.message || error}`;
  } finally {
    $('#refreshDevices').disabled = false;
  }
}

async function selectBroadcastDevice() {
  if (!outputDevices.length) await refreshAudioDevices();
  const selected = cableDevice() || outputDevices.find(device => device.id === $('#outputDevice').value)
    || outputDevices.find(device => device.isDefault) || outputDevices[0];
  if (!selected) throw new Error(getString('audio.noDevices'));
  $('#outputDevice').value = selected.id;
  await api.setWindowsOutput(selected.id);
  await api.saveSettings({ outputDeviceId: selected.id });
  if (!cableDevice()) $('#audioDeviceHelp').textContent = getString('audio.cableMissing');
  return selected;
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
    $('#lanAddress').value = state.addresses[0] || '';
    setServerStatus(true);
    await refreshConnection();
    renderClients(state.clients);
  } catch (error) {
    alert(`${getString('error.serverStart')}\n${error.message || error}`);
  }
}

async function stopServer() {
  await stopAudio();
  try {
    server = await api.stopServer();
    setServerStatus(false);
    await refreshConnection();
    renderClients([]);
  } catch (error) { alert(`${getString('error.serverStop')}\n${error.message || error}`); }
}

async function startAudio() {
  if (broadcastStarting || outputStream) return;
  broadcastStarting = true;
  $('#broadcastButton').disabled = true;
  if (!server.running) await startServer();
  if (!server.running) { broadcastStarting = false; $('#broadcastButton').disabled = false; return; }
  try {
    const device = await selectBroadcastDevice();
    const capture = await api.prepareAudioCapture(device.id);
    audioContext = new AudioContext({ latencyHint: 'interactive', sampleRate: capture.sampleRate });
    await audioContext.audioWorklet.addModule(new URL('audio-processor.js', window.location.href));
    audioWorkletNode = new AudioWorkletNode(audioContext, 'airear-loopback', {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [Math.min(2, Math.max(1, capture.channels))],
    });
    const gain = audioContext.createGain();
    const limiter = audioContext.createDynamicsCompressor();
    limiter.threshold.value = -2;
    limiter.knee.value = 3;
    limiter.ratio.value = 12;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.12;
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    audioWorkletNode.connect(gain).connect(limiter).connect(analyser);
    const destination = audioContext.createMediaStreamDestination();
    analyser.connect(destination);
    outputStream = destination.stream;
    gainNode = gain;
    syncGain();
    await audioContext.resume();
    await api.startAudioCapture();
    openDesktopSocket();
    startMeter();
    setAudioStatus(true);
    await refreshConnection();
  } catch (error) {
    await stopAudio();
    alert(`${getString('error.capture')}\n${error.message || error}`);
  } finally { broadcastStarting = false; }
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

async function stopAudio() {
  cancelAnimationFrame(meterFrame);
  for (const id of [...peers.keys()]) closePeer(id);
  const socket = signalSocket;
  signalSocket = null;
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'broadcast-stopped');
  try { audioWorkletNode?.disconnect(); } catch { /* already disconnected */ }
  audioWorkletNode?.port.close();
  audioWorkletNode = null;
  await api.stopAudioCapture().catch(() => {});
  outputStream = null;
  analyser = null;
  gainNode = null;
  if (audioContext) audioContext.close().catch(() => {});
  audioContext = null;
  $('#meterFill').style.width = '0';
  setAudioStatus(false);
  clearQrImages();
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
  const devicesReady = refreshAudioDevices();
  setTheme($('#theme').value);
  server = appState.server;
  server.addresses = await api.refreshLanAddresses();
  $('#lanAddress').value = server.addresses[0] || '';
  setServerStatus(server.running);
  if (server.running) {
    await refreshConnection();
  }
  await devicesReady;
  renderClients(server.clients || []);
  renderDiagnostics();
}

document.querySelectorAll('.nav-item').forEach(button => button.addEventListener('click', () => showView(button.dataset.target)));
$('#settingsButton').addEventListener('click', () => showView('settings'));
$('#serverButton').addEventListener('click', () => server.running ? stopServer() : startServer());
$('#broadcastButton').addEventListener('click', startAudio);
$('#stopBroadcastButton').addEventListener('click', () => { void stopAudio(); });
$('#refreshAddress').addEventListener('click', refreshLanAddress);
$('#refreshDevices').addEventListener('click', refreshAudioDevices);
$('#outputDevice').addEventListener('change', async () => {
  try {
    const id = $('#outputDevice').value;
    await api.setWindowsOutput(id);
    await api.saveSettings({ outputDeviceId: id });
    if (outputStream) await stopAudio();
  } catch (error) { alert(`${getString('audio.deviceError')}\n${error.message || error}`); }
});
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
api.onServerState(state => {
  if ((server.addresses || []).join(',') !== (state.addresses || []).join(',')) {
    $('#lanAddress').value = '';
    clearQrImages();
    $('#lanAddress').value = state.addresses?.[0] || '';
  }
  server = state;
  setServerStatus(state.running);
  refreshConnection(); renderClients(state.clients); renderDiagnostics();
});
api.onAudioFrame(frame => {
  if (!audioWorkletNode) return;
  const samples = Float32Array.from(frame.samples);
  audioWorkletNode.port.postMessage({ samples: samples.buffer, channels: frame.channels, sampleRate: frame.sampleRate }, [samples.buffer]);
});
api.onAudioError(({ message }) => {
  if (outputStream) {
    void stopAudio().then(() => setAudioStatus(false, `${getString('audio.captureError')} ${message || ''}`.trim()));
  }
});
api.onUpdateState(setUpdateButton);
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if ($('#theme').value === 'system') setTheme('system'); });
initialize().catch(error => { alert(`${getString('error.initialization')}\n${error.message || error}`); }).finally(() => {
  $('#startupNotice').hidden = true;
  languageCheck = setInterval(() => applyLanguage($('#language').value), 2500);
  void languageCheck;
});
