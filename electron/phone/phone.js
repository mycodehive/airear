'use strict';

const $ = selector => document.querySelector(selector);
let translations = {};
let socket = null;
let peer = null;
let peerId = '';
let pendingCandidates = [];
let reconnectTimer = null;
let reconnectDelay = 1000;
let userDisconnected = true;
let isConnected = false;

function textFor(key) {
  return key.split('.').reduce((value, part) => value && value[part], translations) || key;
}

async function loadLanguage(language) {
  try {
    const response = await fetch(`/languages/${language}.json`, { cache: 'no-store' });
    if (!response.ok) return;
    translations = await response.json();
    document.documentElement.lang = language;
    document.querySelectorAll('[data-i18n]').forEach(node => { node.textContent = textFor(node.dataset.i18n); });
  } catch { /* keep current language when the LAN is temporarily unavailable */ }
}

function setStatus(key, className = '') {
  $('#status').textContent = textFor(key);
  $('#status').className = `status ${className}`;
}

function webSocketUrl() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${location.host}/signal`;
}

function connect() {
  const pin = $('#pin').value.trim();
  if (!/^\d{8}$/.test(pin)) {
    setStatus('phone.pinInvalid', 'error');
    $('#pin').focus();
    return;
  }
  userDisconnected = false;
  isConnected = false;
  $('#connect').disabled = true;
  $('#disconnect').disabled = false;
  setStatus('phone.connecting');
  socket = new WebSocket(webSocketUrl());
  socket.onopen = () => socket.send(JSON.stringify({ type: 'join', pin }));
  socket.onmessage = event => receive(JSON.parse(event.data));
  socket.onerror = () => setStatus('phone.networkError', 'error');
  socket.onclose = () => {
    closePeer(false);
    if (!userDisconnected) scheduleReconnect();
  };
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  setStatus('phone.reconnecting');
  reconnectTimer = setTimeout(() => {
    reconnectDelay = Math.min(20000, reconnectDelay * 2);
    connect();
  }, reconnectDelay);
}

async function receive(message) {
  if (message.type === 'error') {
    if (message.code === 'incorrect-pin') setStatus('phone.pinIncorrect', 'error');
    else if (message.code === 'capacity') setStatus('phone.capacity', 'error');
    else if (message.code === 'not-streaming') setStatus('phone.notStreaming', 'error');
    else setStatus('phone.networkError', 'error');
    if (['incorrect-pin', 'capacity'].includes(message.code)) {
      userDisconnected = true;
      $('#connect').disabled = false;
      $('#disconnect').disabled = true;
    }
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'connection-refused');
    return;
  }
  if (message.type === 'joined') {
    peerId = message.peerId;
    reconnectDelay = 1000;
    await createOffer();
  } else if (message.type === 'answer') {
    if (!peer) return;
    try {
      await peer.setRemoteDescription({ type: 'answer', sdp: message.sdp });
      for (const candidate of pendingCandidates.splice(0)) await peer.addIceCandidate(candidate).catch(() => {});
      setStatus('phone.waitingAudio');
    } catch { setStatus('phone.connectionFailed', 'error'); }
  } else if (message.type === 'ice') {
    if (peer?.remoteDescription) peer.addIceCandidate(message.candidate).catch(() => {});
    else pendingCandidates.push(message.candidate);
  } else if (message.type === 'state') {
    if (message.state === 'connected') setStatus('phone.connected', 'connected');
  }
}

async function createOffer() {
  peer = new RTCPeerConnection({ iceServers: [], bundlePolicy: 'max-bundle' });
  peer.addTransceiver('audio', { direction: 'recvonly' });
  peer.onicecandidate = event => { if (event.candidate && socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ice', candidate: event.candidate })); };
  peer.ontrack = async event => {
    const stream = event.streams[0] || new MediaStream([event.track]);
    $('#audio').srcObject = stream;
    try {
      await $('#audio').play();
      isConnected = true;
      setStatus('phone.connected', 'connected');
    } catch {
      setStatus('phone.tapPlay');
    }
  };
  peer.onconnectionstatechange = () => {
    if (peer?.connectionState === 'connected') {
      isConnected = true;
      setStatus('phone.connected', 'connected');
    } else if (['failed', 'disconnected'].includes(peer?.connectionState) && !userDisconnected) {
      setStatus('phone.networkInterrupted');
    }
  };
  try {
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    socket.send(JSON.stringify({ type: 'offer', sdp: peer.localDescription.sdp }));
    setStatus('phone.negotiating');
  } catch { setStatus('phone.connectionFailed', 'error'); }
}

function closePeer(clearAudio = true) {
  if (peer) { try { peer.close(); } catch { /* already closed */ } }
  peer = null;
  peerId = '';
  pendingCandidates = [];
  isConnected = false;
  if (clearAudio) $('#audio').srcObject = null;
}

function disconnect() {
  userDisconnected = true;
  clearTimeout(reconnectTimer);
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'leave' }));
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'user-disconnected');
  socket = null;
  closePeer();
  $('#connect').disabled = false;
  $('#disconnect').disabled = true;
  setStatus('phone.disconnected');
}

$('#connect').addEventListener('click', connect);
$('#disconnect').addEventListener('click', disconnect);
$('#pin').addEventListener('keydown', event => { if (event.key === 'Enter') connect(); });
const browserLanguage = (navigator.language || 'en').toLowerCase();
$('#language').value = browserLanguage.startsWith('ko') ? 'ko' : (browserLanguage.startsWith('ja') ? 'ja' : 'en');
$('#language').addEventListener('change', () => loadLanguage($('#language').value));
loadLanguage($('#language').value);
setInterval(() => loadLanguage($('#language').value), 3000);
window.addEventListener('online', () => { if (!userDisconnected && !isConnected) scheduleReconnect(); });
window.addEventListener('pageshow', () => {
  if ($('#audio').srcObject && $('#audio').paused && !userDisconnected) setStatus('phone.tapPlay');
});
