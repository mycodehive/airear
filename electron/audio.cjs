'use strict';

function toFloat32(samples, format) {
  if (format === 'f32') return Float32Array.from(samples);
  const output = new Float32Array(samples.length);
  const converters = {
    f64: value => value,
    i8: value => value / 128,
    i16: value => value / 32768,
    i24: value => value / 8388608,
    i32: value => value / 2147483648,
    u8: value => (value - 128) / 128,
    u16: value => (value - 32768) / 32768,
    u24: value => (value - 8388608) / 8388608,
    u32: value => (value - 2147483648) / 2147483648,
  };
  const convert = converters[format];
  if (!convert) throw new Error(`Unsupported WASAPI sample format: ${format}`);
  for (let index = 0; index < samples.length; index++) output[index] = Math.max(-1, Math.min(1, convert(samples[index])));
  return output;
}

class AudioCaptureService {
  constructor({ cpal = require('node-cpal'), onFrame = () => {}, onError = () => {} } = {}) {
    this.cpal = cpal;
    this.onFrame = onFrame;
    this.onError = onError;
    this.stream = null;
    this.active = false;
  }

  listOutputDevices() {
    const api = this.cpal.convenience;
    const devices = api.getDevices({ direction: 'output' });
    return devices
      .filter(device => device.supportsOutput && device.supportsLoopback)
      .map(device => {
        let config = null;
        try { config = api.getDefaultOutputConfig(device.deviceId); } catch { /* device may have disconnected */ }
        return {
          id: device.deviceId,
          name: device.name,
          isDefault: !!device.isDefaultOutput,
          sampleRate: config?.sampleRate || 48000,
          channels: config?.channels || 2,
          sampleFormat: config?.sampleFormat || 'f32',
        };
      });
  }

  async prepare(deviceId) {
    await this.stop();
    const device = this.cpal.convenience.getDeviceById(deviceId);
    if (!device?.supportsOutput || !device.supportsLoopback) throw new Error('The selected output device does not support WASAPI loopback capture.');
    const current = this.listOutputDevices().find(item => item.id === deviceId);
    if (!current) throw new Error('The selected output device is no longer available. Refresh the device list and try again.');
    const config = this.cpal.convenience.getDefaultOutputConfig(deviceId);
    const captureConfig = {
      sampleRate: config.sampleRate,
      channels: config.channels,
      sampleFormat: config.sampleFormat,
      bufferSize: config.bufferSize,
    };
    this.stream = await this.cpal.convenience.createLoopbackStream({
      deviceId,
      config: captureConfig,
      queueCapacityBuffers: 12,
      autoStart: false,
      onData: samples => {
        if (!this.active) return;
        try {
          this.onFrame({ samples: toFloat32(samples, config.sampleFormat), sampleRate: config.sampleRate, channels: config.channels });
        } catch (error) { this.onError(error); }
      },
      onError: error => this.onError(error),
    });
    return { sampleRate: config.sampleRate, channels: config.channels, sampleFormat: config.sampleFormat };
  }

  start() {
    if (!this.stream) throw new Error('Prepare an output device before starting capture.');
    this.active = true;
    this.stream.play();
    return true;
  }

  async stop() {
    this.active = false;
    const stream = this.stream;
    this.stream = null;
    if (stream) await stream.close();
  }
}

function preferredCableDevice(devices) {
  return devices.find(device => /cable\s*input/i.test(device.name) && /vb\s*-?\s*audio/i.test(device.name))
    || devices.find(device => /cable\s*input/i.test(device.name));
}

module.exports = { AudioCaptureService, preferredCableDevice, toFloat32 };
