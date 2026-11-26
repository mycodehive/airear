'use strict';
const { execFile, spawn } = require('node:child_process');
const { promisify } = require('node:util');
const run = promisify(execFile);
class LinuxAudioCaptureService {
  constructor({ onFrame = () => {}, onError = () => {}, execute = run, launch = spawn } = {}) {
    Object.assign(this, { onFrame, onError, execute, launch });
    this.stream = null;
    this.monitor = null;
  }
  async pactl(...args) {
    try { return (await this.execute('pactl', args, { timeout: 5000, maxBuffer: 1024 * 1024 })).stdout.trim(); }
    catch (error) { throw new Error(`PulseAudio/PipeWire unavailable. Install pulseaudio-utils and run in your desktop audio session. ${error.code || ''}`); }
  }
  async listOutputDevices() {
    const [json, current] = await Promise.all([this.pactl('--format=json', 'list', 'sinks'), this.pactl('get-default-sink')]);
    return JSON.parse(json).filter(sink => sink.name).map(sink => ({
      id: sink.name, name: sink.description || sink.name, isDefault: sink.name === current, monitor: sink.monitor_source_name || (typeof sink.monitor_source === 'string' ? sink.monitor_source : `${sink.name}.monitor`),
    }));
  }
  async setOutput(id) {
    if (!(await this.listOutputDevices()).some(device => device.id === id)) throw new Error('Output device is unavailable.');
    await this.pactl('set-default-sink', id);
    // Existing applications may retain per-stream routing; do not reroute them silently.
    return true;
  }
  async prepare(id) {
    await this.stop();
    const device = (await this.listOutputDevices()).find(device => device.id === id);
    if (!device) throw new Error('Output device is unavailable. Refresh the device list.');
    this.monitor = device.monitor;
    return { sampleRate: 48000, channels: 2, sampleFormat: 'f32' };
  }
  async start() {
    if (!this.monitor) throw new Error('Prepare an output device first.');
    const child = this.launch('parec', ['--raw', `--device=${this.monitor}`, '--format=float32le', '--rate=48000', '--channels=2', '--latency-msec=40']);
    this.stream = child;
    let pending = Buffer.alloc(0);
    let failure = '';
    child.stderr.on('data', data => { failure = (failure + data.toString()).slice(-1000); });
    child.stdout.on('data', data => {
      if (this.stream !== child) return;
      const bytes = Buffer.concat([pending, data]);
      const length = bytes.length - bytes.length % 8;
      pending = Buffer.from(bytes.subarray(length));
      if (!length) return;
      const samples = new Float32Array(length / 4);
      for (let i = 0; i < samples.length; i++) samples[i] = bytes.readFloatLE(i * 4);
      this.onFrame({ samples, sampleRate: 48000, channels: 2 });
    });
    child.on('error', error => { if (this.stream === child) { this.stream = null; this.onError(error); } });
    child.on('exit', code => {
      if (this.stream === child) { this.stream = null; this.onError(new Error(failure || `parec exited (${code})`)); }
    });
    await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
    return true;
  }
  async stop() {
    const child = this.stream;
    this.stream = null;
    if (!child || child.exitCode !== null) return;
    await new Promise(resolve => {
      const timer = setTimeout(() => { child.kill('SIGKILL'); resolve(); }, 1500);
      child.once('exit', () => { clearTimeout(timer); resolve(); });
      child.kill('SIGTERM');
    });
  }
}
module.exports = { LinuxAudioCaptureService };
