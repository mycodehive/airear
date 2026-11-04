'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { AirEarServer, getLanAddresses, isAllowedLanAddress, isPrivateIPv4 } = require('./server.cjs');

test('private IPv4 detection rejects public and link-local addresses', () => {
  assert.equal(isPrivateIPv4('192.168.0.45'), true);
  assert.equal(isPrivateIPv4('10.0.0.8'), true);
  assert.equal(isPrivateIPv4('172.20.0.4'), true);
  assert.equal(isPrivateIPv4('164.90.1.2'), false);
  assert.equal(isPrivateIPv4('169.254.1.2'), false);
  assert.equal(isPrivateIPv4('not-an-ip'), false);
  assert.equal(isAllowedLanAddress('::ffff:192.168.0.2'), true);
  assert.equal(isAllowedLanAddress('164.90.1.2'), false);
});

test('LAN address list filters public adapters and prefers 192.168 addresses', () => {
  const addresses = getLanAddresses({
    wifi: [{ address: '192.168.0.45', family: 'IPv4', internal: false }],
    vpn: [{ address: '164.90.1.2', family: 'IPv4', internal: false }],
    loopback: [{ address: '127.0.0.1', family: 'IPv4', internal: true }],
    private: [{ address: '10.0.0.2', family: 4, internal: false }],
  });
  assert.deepEqual(addresses, ['192.168.0.45', '10.0.0.2']);
});

test('LAN server serves receiver files and health status', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'airear-electron-'));
  const web = path.join(root, 'web');
  const languages = path.join(root, 'languages');
  fs.mkdirSync(web);
  fs.mkdirSync(languages);
  fs.writeFileSync(path.join(web, 'index.html'), '<h1>phone</h1>');
  fs.writeFileSync(path.join(languages, 'en.json'), '{"test":"ok"}');
  const server = new AirEarServer({ phoneRoot: web, languageRoot: languages });
  t.after(async () => { await server.stop(); fs.rmSync(root, { recursive: true, force: true }); });
  const state = await server.start(0);
  const health = await fetch(`http://127.0.0.1:${state.port}/api/health`);
  assert.deepEqual(await health.json(), { ok: true, version: '2.0.0' });
  const page = await fetch(`http://127.0.0.1:${state.port}/`);
  assert.equal(await page.text(), '<h1>phone</h1>');
  const language = await fetch(`http://127.0.0.1:${state.port}/languages/en.json`);
  assert.deepEqual(await language.json(), { test: 'ok' });
  assert.equal(server.snapshot().running, true);
});
