'use strict';

class AirEarLoopbackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.current = null;
    this.position = 0;
    this.maxQueuedFrames = 24000;
    this.queuedFrames = 0;
    this.port.onmessage = event => {
      const message = event.data;
      if (!message?.samples || !message.channels || !message.sampleRate) return;
      const samples = new Float32Array(message.samples);
      const frames = Math.floor(samples.length / message.channels);
      if (!frames) return;
      this.queue.push({ samples, channels: message.channels, sampleRate: message.sampleRate, frames });
      this.queuedFrames += frames;
      while (this.queuedFrames > this.maxQueuedFrames && this.queue.length > 1) {
        this.queuedFrames -= this.queue.shift().frames;
      }
    };
  }

  process(_inputs, outputs) {
    const channels = outputs[0] || [];
    for (const channel of channels) channel.fill(0);
    if (!channels.length) return true;

    const frameCount = channels[0].length;
    for (let frame = 0; frame < frameCount; frame++) {
      if (!this.current) {
        this.current = this.queue.shift() || null;
        this.position = 0;
      }
      if (!this.current) continue;

      const source = this.current;
      const sourceFrame = Math.min(source.frames - 1, Math.floor(this.position));
      const nextFrame = Math.min(source.frames - 1, sourceFrame + 1);
      const fraction = this.position - sourceFrame;
      const sampleAt = channel => {
        if (source.channels === 1) return source.samples[sourceFrame];
        const selected = Math.min(channel, source.channels - 1);
        const current = source.samples[sourceFrame * source.channels + selected];
        const next = source.samples[nextFrame * source.channels + selected];
        return current + (next - current) * fraction;
      };
      for (let channel = 0; channel < channels.length; channel++) {
        if (source.channels === 1 && channels.length > 1) channels[channel][frame] = sampleAt(0);
        else if (channels.length === 1 && source.channels > 1) {
          let sum = 0;
          for (let input = 0; input < source.channels; input++) sum += sampleAt(input);
          channels[channel][frame] = sum / source.channels;
        } else channels[channel][frame] = sampleAt(channel);
      }

      this.position += source.sampleRate / sampleRate;
      while (this.current && this.position >= this.current.frames) {
        this.position -= this.current.frames;
        this.queuedFrames -= this.current.frames;
        this.current = this.queue.shift() || null;
      }
    }
    return true;
  }
}

registerProcessor('airear-loopback', AirEarLoopbackProcessor);
