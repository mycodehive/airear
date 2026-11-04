'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { AudioCaptureService, preferredCableDevice, toFloat32 } = require('./audio.cjs');

const device = (id, name, defaults = {}) => ({ id, name, isDefault: false, sampleRate: 48000, channels: 2, sampleFormat: 'f32', ...defaults });

test('broadcast start prefers the VB-Audio CABLE Input endpoint', () => {
  const devices = [device('speaker', 'Speakers (Realtek)'), device('cable', 'CABLE Input (VB-Audio Virtual Cable)')];
  assert.equal(preferredCableDevice(devices).id, 'cable');
});

test('cable matching handles the common shortened Windows endpoint label', () => {
  assert.equal(preferredCableDevice([device('cable', 'CABLE Input')]).id, 'cable');
  assert.equal(preferredCableDevice([device('speaker', 'Speakers')]), undefined);
});

test('audio capture enumerates loopback endpoints and prepares the selected output endpoint', async () => {
  let capturedOptions;
  let callback;
  let started = false;
  let closed = false;
  const devices = [
    { deviceId: 'wasapi:cable', name: 'CABLE Input (VB-Audio Virtual Cable)', supportsOutput: true, supportsLoopback: true, isDefaultOutput: false },
    { deviceId: 'wasapi:mic', name: 'Microphone', supportsOutput: false, supportsLoopback: false, isDefaultOutput: false },
  ];
  const config = { sampleRate: 48000, channels: 2, sampleFormat: 'f32', bufferSize: { type: 'default' } };
  const cpal = { convenience: {
    getDevices: () => devices,
    getDeviceById: id => devices.find(item => item.deviceId === id),
    getDefaultOutputConfig: () => config,
    createLoopbackStream: async options => {
      capturedOptions = options;
      callback = options.onData;
      return { play: () => { started = true; }, close: async () => { closed = true; } };
    },
  } };
  const frames = [];
  const service = new AudioCaptureService({ cpal, onFrame: frame => frames.push(frame) });
  assert.deepEqual(service.listOutputDevices().map(item => item.id), ['wasapi:cable']);
  assert.deepEqual(await service.prepare('wasapi:cable'), { sampleRate: 48000, channels: 2, sampleFormat: 'f32' });
  assert.equal(capturedOptions.deviceId, 'wasapi:cable');
  assert.equal(capturedOptions.autoStart, false);
  service.start();
  assert.equal(started, true);
  callback(new Float32Array([0, 0.5, -0.5, 1]));
  assert.deepEqual(Array.from(frames[0].samples), [0, 0.5, -0.5, 1]);
  assert.equal(frames[0].sampleRate, 48000);
  await service.stop();
  assert.equal(closed, true);
});

test('integer WASAPI samples are normalized into float audio frames', () => {
  assert.deepEqual(Array.from(toFloat32(new Int16Array([-32768, 0, 32767]), 'i16')), [-1, 0, 32767 / 32768]);
  assert.deepEqual(Array.from(toFloat32(new Uint8Array([0, 128, 255]), 'u8')), [-1, 0, 127 / 128]);
});
