'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { LinuxAudioCaptureService } = require('./linux-audio.cjs');
test('Linux output selection uses the sink monitor and configures the default output', async () => {
  const calls = [];
  const audio = new LinuxAudioCaptureService({ execute: async (_command, args) => {
    calls.push(args);
    return { stdout: args[0] === '--format=json' ? JSON.stringify([{ name: 'speakers', description: 'Speakers', monitor_source_name: 'speakers.monitor' }]) : 'speakers' };
  } });
  assert.equal((await audio.listOutputDevices())[0].isDefault, true);
  assert.deepEqual(await audio.prepare('speakers'), { sampleRate: 48000, channels: 2, sampleFormat: 'f32' });
  assert.equal(audio.monitor, 'speakers.monitor');
  await audio.setOutput('speakers');
  assert.ok(calls.some(args => args.join(' ') === 'set-default-sink speakers'));
  await assert.rejects(audio.prepare('missing'), /unavailable/);
});
test('missing Linux audio tools produces an actionable error', async () => {
  const audio = new LinuxAudioCaptureService({ execute: async () => { throw Object.assign(new Error(), { code: 'ENOENT' }); } });
  await assert.rejects(audio.listOutputDevices(), /pulseaudio-utils/);
});
test('real PulseAudio monitor captures generated audio', { skip: !process.env.AIREAR_LINUX_AUDIO_TEST, timeout: 10000 }, async () => {
  const { spawn } = require('node:child_process');
  let received;
  const signal = new Promise(resolve => { received = resolve; });
  const audio = new LinuxAudioCaptureService({ onFrame: frame => { if (frame.samples.some(value => Math.abs(value) > 0.01)) received(); } });
  await audio.prepare('airear_test');
  await audio.start();
  const player = spawn('pacat', ['--playback', '--raw', '--device=airear_test', '--format=float32le', '--rate=48000', '--channels=2']);
  player.on('error', () => {});
  const bytes = Buffer.alloc(48000 * 2 * 4);
  for (let i = 0; i < 48000; i++) { const value = Math.sin(i * Math.PI * 2 * 440 / 48000) * 0.2; bytes.writeFloatLE(value, i * 8); bytes.writeFloatLE(value, i * 8 + 4); }
  player.stdin.end(bytes);
  let timer;
  try { await Promise.race([signal, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('No monitor audio received')), 5000); })]); }
  finally { clearTimeout(timer); player.kill(); await audio.stop(); }
});
