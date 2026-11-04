'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const QRCode = require('qrcode');

const root = path.join(__dirname, '..');

test('desktop QR is mounted in both dashboard and connection views', () => {
  const html = fs.readFileSync(path.join(__dirname, 'desktop', 'index.html'), 'utf8');
  assert.match(html, /<section id="connection"[^>]*>[\s\S]*?<img id="connectionQr" data-connection-qr/u);
  assert.match(html, /<img id="qr" data-connection-qr/u);
  assert.equal((html.match(/data-connection-qr/g) || []).length, 2);
});

test('QR generator produces an embeddable image for the shown LAN URL', async () => {
  const url = 'http://192.168.0.45:8765/';
  const dataUrl = await QRCode.toDataURL(url, { width: 240, margin: 2, errorCorrectionLevel: 'M' });
  assert.match(dataUrl, /^data:image\/png;base64,/u);
  assert.ok(Buffer.from(dataUrl.split(',')[1], 'base64').length > 500);
  assert.equal(fs.readFileSync(path.join(root, 'electron', 'desktop', 'desktop.js'), 'utf8').includes("querySelectorAll('[data-connection-qr]')"), true);
});
