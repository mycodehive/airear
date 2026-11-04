'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const express = require('express');
const { WebSocketServer, WebSocket } = require('ws');

const LAN_CIDRS = [
  ['10.0.0.0', 8], ['172.16.0.0', 12], ['192.168.0.0', 16],
];

function ipv4Number(text) {
  if (typeof text !== 'string') return null;
  const parts = text.split('.');
  if (parts.length !== 4 || parts.some(p => !/^\d{1,3}$/.test(p) || Number(p) > 255)) return null;
  return parts.reduce((n, p) => ((n * 256) + Number(p)) >>> 0, 0);
}

function isPrivateIPv4(text) {
  const n = ipv4Number(text);
  if (n === null) return false;
  return LAN_CIDRS.some(([base, bits]) => {
    const b = ipv4Number(base);
    const mask = (0xffffffff << (32 - bits)) >>> 0;
    return (n & mask) === (b & mask);
  });
}

function getLanAddresses(interfaces) {
  if (!interfaces) {
    try { interfaces = os.networkInterfaces(); }
    catch { return []; }
  }
  const result = new Set();
  for (const entries of Object.values(interfaces)) {
    for (const entry of entries || []) {
      const address = entry.family === 'IPv4' || entry.family === 4 ? entry.address : '';
      if (!entry.internal && isPrivateIPv4(address)) result.add(address);
    }
  }
  return [...result].sort((a, b) => {
    const a192 = a.startsWith('192.168.') ? 0 : 1;
    const b192 = b.startsWith('192.168.') ? 0 : 1;
    return a192 - b192 || ipv4Number(a) - ipv4Number(b);
  });
}

function normalizedRemoteAddress(value = '') {
  const address = value.startsWith('::ffff:') ? value.slice(7) : value;
  return address;
}

function isAllowedLanAddress(value) {
  const address = normalizedRemoteAddress(value);
  return address === '127.0.0.1' || address === '::1' || isPrivateIPv4(address);
}

class AirEarServer {
  constructor({ phoneRoot, languageRoot, onChange = () => {}, maxPeers = 4 } = {}) {
    this.phoneRoot = phoneRoot;
    this.languageRoot = languageRoot;
    this.onChange = onChange;
    this.maxPeers = maxPeers;
    this.httpServer = null;
    this.wss = null;
    this.port = 0;
    this.pin = '';
    this.desktopToken = '';
    this.desktop = null;
    this.peers = new Map();
    this.attempts = new Map();
  }

  async start(port = 8765) {
    if (this.httpServer) return this.snapshot();
    this.pin = String(crypto.randomInt(0, 100000000)).padStart(8, '0');
    this.desktopToken = crypto.randomBytes(32).toString('hex');
    const app = express();
    app.disable('x-powered-by');
    app.use((req, res, next) => {
      const remote = normalizedRemoteAddress(req.socket.remoteAddress || '');
      if (!isAllowedLanAddress(remote)) return res.sendStatus(403);
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.setHeader('Referrer-Policy', 'no-referrer');
      res.setHeader('Cache-Control', 'no-store');
      res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' ws: wss:; media-src 'self' blob:; frame-ancestors 'none'");
      next();
    });
    app.get('/api/health', (req, res) => res.json({ ok: true, version: '2.0.0' }));
    app.get('/api/info', (req, res) => res.json({ name: 'AirEar', version: '2.0.0' }));
    app.get('/languages/:language.json', (req, res) => {
      const language = req.params.language;
      if (!['ko', 'en', 'ja'].includes(language)) return res.sendStatus(404);
      const file = path.join(this.languageRoot, `${language}.json`);
      if (!fs.existsSync(file)) return res.sendStatus(404);
      res.type('application/json').sendFile(file);
    });
    app.use(express.static(this.phoneRoot, { index: 'index.html', extensions: ['html'] }));
    this.httpServer = http.createServer(app);
    this.wss = new WebSocketServer({ noServer: true, maxPayload: 128 * 1024 });
    this.httpServer.on('upgrade', (req, socket, head) => {
      const remote = normalizedRemoteAddress(req.socket.remoteAddress || '');
      if (!isAllowedLanAddress(remote) || new URL(req.url, 'http://localhost').pathname !== '/signal') {
        socket.destroy();
        return;
      }
      this.wss.handleUpgrade(req, socket, head, ws => this._connected(ws, remote));
    });
    await new Promise((resolve, reject) => {
      const onError = error => { this.httpServer.off('listening', onListen); reject(error); };
      const onListen = () => { this.httpServer.off('error', onError); resolve(); };
      this.httpServer.once('error', onError);
      this.httpServer.once('listening', onListen);
      this.httpServer.listen(port, '0.0.0.0');
    });
    this.port = this.httpServer.address().port;
    this.onChange(this.snapshot());
    return this.snapshot();
  }

  _connected(ws, address) {
    const client = { ws, address, role: '', peerId: '', connectedAt: Date.now() };
    ws.on('message', raw => {
      let message;
      try { message = JSON.parse(raw.toString()); } catch { return this._close(ws, 1008, 'invalid-json'); }
      if (!message || typeof message.type !== 'string') return;
      if (!client.role) return this._register(client, message);
      if (client.role === 'phone') return this._phoneMessage(client, message);
      if (client.role === 'desktop') return this._desktopMessage(client, message);
    });
    ws.on('close', () => this._disconnected(client));
    ws.on('error', () => this._disconnected(client));
  }

  _register(client, message) {
    if (message.type === 'desktop') {
      if (message.token !== this.desktopToken || this.desktop) return this._close(client.ws, 1008, 'unauthorized');
      client.role = 'desktop';
      this.desktop = client;
      this._send(client.ws, { type: 'ready', peers: this._peerList() });
      this.onChange(this.snapshot());
      return;
    }
    if (message.type !== 'join') return this._close(client.ws, 1008, 'register-first');
    const now = Date.now();
    const previous = (this.attempts.get(client.address) || []).filter(time => now - time < 60000);
    if (previous.length >= 6) return this._close(client.ws, 1008, 'rate-limit');
    if (typeof message.pin !== 'string' || !/^\d{8}$/.test(message.pin) || message.pin !== this.pin) {
      previous.push(now);
      this.attempts.set(client.address, previous);
      return this._send(client.ws, { type: 'error', code: 'incorrect-pin' });
    }
    if (this.peers.size >= this.maxPeers) return this._send(client.ws, { type: 'error', code: 'capacity' });
    if (!this.desktop || this.desktop.ws.readyState !== WebSocket.OPEN) return this._send(client.ws, { type: 'error', code: 'not-streaming' });
    client.role = 'phone';
    client.peerId = crypto.randomUUID();
    this.peers.set(client.peerId, client);
    this._send(client.ws, { type: 'joined', peerId: client.peerId });
    this._send(this.desktop.ws, { type: 'peer-joined', peerId: client.peerId, address: client.address });
    this.onChange(this.snapshot());
  }

  _phoneMessage(client, message) {
    if (!['offer', 'ice', 'leave'].includes(message.type)) return;
    if (message.type === 'leave') return this._removePeer(client.peerId, 'phone-left');
    if (this.desktop?.ws.readyState === WebSocket.OPEN) {
      this._send(this.desktop.ws, { ...message, peerId: client.peerId });
    }
  }

  _desktopMessage(client, message) {
    if (message.type === 'ice' || message.type === 'answer') {
      const phone = this.peers.get(message.peerId);
      if (phone?.ws.readyState === WebSocket.OPEN) this._send(phone.ws, { ...message, peerId: undefined });
    } else if (message.type === 'peer-state') {
      const phone = this.peers.get(message.peerId);
      if (phone?.ws.readyState === WebSocket.OPEN) this._send(phone.ws, { type: 'state', state: String(message.state || '') });
    } else if (message.type === 'close-peer') {
      this._removePeer(message.peerId, 'receiver-removed');
    }
  }

  _disconnected(client) {
    if (client.role === 'phone') this._removePeer(client.peerId, 'phone-disconnected', false);
    if (client === this.desktop) {
      this.desktop = null;
      for (const [peerId, phone] of this.peers) {
        this._send(phone.ws, { type: 'error', code: 'stream-ended' });
        this._removePeer(peerId, 'stream-ended');
      }
    }
    this.onChange(this.snapshot());
  }

  _removePeer(peerId, reason, closeSocket = true) {
    const client = this.peers.get(peerId);
    if (!client) return;
    this.peers.delete(peerId);
    if (closeSocket && client.ws.readyState === WebSocket.OPEN) {
      if (reason === 'receiver-removed') this._send(client.ws, { type: 'error', code: reason });
      this._close(client.ws, 1000, reason);
    }
    if (this.desktop?.ws.readyState === WebSocket.OPEN) this._send(this.desktop.ws, { type: 'close-peer', peerId, reason });
    this.onChange(this.snapshot());
  }

  _send(ws, value) {
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(value));
  }

  _close(ws, code, reason) {
    try { ws.close(code, String(reason).slice(0, 100)); } catch { ws.terminate(); }
  }

  _peerList() {
    return [...this.peers].map(([id, item]) => ({ id, address: item.address, connectedAt: item.connectedAt }));
  }

  snapshot() {
    return { running: !!this.httpServer, port: this.port, pin: this.pin, addresses: getLanAddresses(), clients: this._peerList(), desktopConnected: !!this.desktop };
  }

  async stop() {
    if (!this.httpServer) return;
    for (const [peerId] of this.peers) this._removePeer(peerId, 'server-stopped');
    if (this.desktop) this._close(this.desktop.ws, 1000, 'server-stopped');
    this.wss.close();
    const server = this.httpServer;
    this.httpServer = null;
    this.desktop = null;
    this.port = 0;
    this.pin = '';
    this.desktopToken = '';
    await new Promise(resolve => server.close(() => resolve()));
    this.onChange(this.snapshot());
  }
}

module.exports = { AirEarServer, getLanAddresses, isPrivateIPv4, isAllowedLanAddress };
