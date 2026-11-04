'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

test('phone can retry after the LAN server is running but audio has not started', async () => {
  const listeners = new Map();
  const timers = [];
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: id === 'pin' ? '12345678' : '',
      disabled: false,
      className: '',
      textContent: '',
      srcObject: null,
      addEventListener: (name, callback) => listeners.set(`${id}:${name}`, callback),
      focus() {},
    });
    return elements.get(id);
  };
  const sockets = [];
  class FakeWebSocket {
    static OPEN = 1;
    static CLOSING = 2;
    static CLOSED = 3;
    constructor() { this.readyState = 0; this.sent = []; sockets.push(this); }
    send(value) { this.sent.push(JSON.parse(value)); }
    close() { this.readyState = FakeWebSocket.CLOSED; }
  }
  const context = {
    document: {
      querySelector: selector => element(selector.slice(1)),
      querySelectorAll: () => [],
      documentElement: {},
    },
    navigator: { language: 'en-US' },
    location: { protocol: 'http:', host: '192.168.0.45:8765' },
    window: { addEventListener() {} },
    WebSocket: FakeWebSocket,
    fetch: async () => ({ ok: true, json: async () => ({ phone: { notStreaming: 'Start broadcasting on the PC first.' } }) }),
    setInterval: () => 1,
    setTimeout: callback => { timers.push(callback); return timers.length; },
    clearTimeout() {},
    MediaStream: class {},
    RTCPeerConnection: class {},
    console,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'phone.js'), 'utf8'), context, { filename: 'phone.js' });
  await new Promise(resolve => setImmediate(resolve));

  listeners.get('connect:click')();
  const socket = sockets[0];
  socket.readyState = FakeWebSocket.OPEN;
  socket.onopen();
  socket.onmessage({ data: JSON.stringify({ type: 'error', code: 'not-streaming' }) });
  await new Promise(resolve => setImmediate(resolve));
  socket.onclose();

  assert.equal(element('status').textContent, 'Start broadcasting on the PC first.');
  assert.equal(element('connect').disabled, false);
  assert.equal(element('disconnect').disabled, true);
  assert.equal(timers.length, 0);
});
