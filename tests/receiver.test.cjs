// Behavioral receiver checks with simulated DOM/WebRTC; no physical-browser claims.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/airear/web/app.js'), 'utf8');

function receiver() {
  const elements = new Map(), connections = [], calls = [], events = new Map(), timers = new Map();
  let timerId = 0;
  class Element {
    constructor() { this.listeners = new Map(); this.value = '12345678'; this.paused = true; this.srcObject = null; this.playCount = 0; this.pauseCount = 0; this.failPlay = false; }
    addEventListener(name, callback) { this.listeners.set(name, callback); }
    setAttribute() {}
    appendChild() {}
    replaceChildren() {}
    async play() { this.playCount++; if (this.failPlay) throw new Error('Autoplay blocked'); this.paused = false; }
    pause() { this.pauseCount++; this.paused = true; }
    emit(name) { return this.listeners.get(name)?.(); }
  }
  const element = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  class Peer {
    constructor() { this.connectionState = 'new'; this.iceGatheringState = 'complete'; this.closeCount = 0; connections.push(this); }
    addTransceiver() {}
    async createOffer() { return {type:'offer', sdp:'test'}; }
    async setLocalDescription(value) { this.localDescription = value; }
    async setRemoteDescription() { this.connectionState = 'connected'; this.onconnectionstatechange?.(); }
    async getStats() { return new Map(); }
    close() { this.closeCount++; this.connectionState = 'closed'; }
  }
  const sandbox = {
    document: {getElementById:element, createElement:()=>new Element(), documentElement:{}, querySelector:()=>new Element(), querySelectorAll:()=>[]},
    navigator: {language:'en'}, localStorage:{getItem:()=>null,setItem:()=>{}}, location:{protocol:'http:'},
    RTCPeerConnection:Peer, MediaStream:class { constructor(tracks) { this.tracks=tracks; } },
    AbortSignal:{timeout:()=>undefined},
    setInterval:()=>1, clearInterval:()=>{},
    setTimeout:(callback, delay)=>{const id=++timerId;timers.set(id,{callback,delay});return id;},
    clearTimeout:id=>timers.delete(id),
    fetch:async (url,options={})=>{
      calls.push({url,options});
      let value={};
      if(url==='/languages') value=[{code:'en',name:'English'}];
      else if(url.startsWith('/languages/')) value={web:{receiving:'Receiving', paused:'Paused', playback_stopped:'Tap to play', connected:'Connected'}};
      else if(url==='/api/auth') value={token:'test-token'};
      else if(url==='/api/offer') value={id:'peer-1',type:'answer',sdp:'answer'};
      return {ok:true,status:options.method==='DELETE'?204:200,json:async()=>value};
    },
    // Any accidental Web Audio dependency makes the test fail immediately.
    AudioContext:class {constructor(){throw Error('Unexpected AudioContext');}}
  };
  sandbox.window={RTCPeerConnection:Peer, AudioContext:sandbox.AudioContext,addEventListener:(name,callback)=>events.set(name,callback)};
  const context=vm.createContext(sandbox);
  vm.runInContext(source,context);
  return {
    element,connections,calls,events,timers,
    async connect() { await vm.runInContext('connect(true)',context); return connections.at(-1); },
    async track(peer) { const track={kind:'audio'}; await peer.ontrack({track,receiver:{jitterBufferTarget:0}}); return track; },
    emit(name) { return events.get(name)?.({persisted:true}); }
  };
}

test('remote stream uses native audio.play without constructing AudioContext',async()=>{
  const ui=receiver(), peer=await ui.connect(), track=await ui.track(peer);
  assert.equal(ui.element('audio').playCount,1);
  assert.equal(ui.element('audio').srcObject.tracks[0],track);
  assert.equal(peer.closeCount,0);
});

test('blocked native play retains peer and user tap retries the same stream',async()=>{
  const ui=receiver(),peer=await ui.connect();ui.element('audio').failPlay=true;
  await ui.track(peer);
  const stream=ui.element('audio').srcObject;
  assert.equal(peer.closeCount,0);assert.equal(ui.element('connect').disabled,false);
  ui.element('audio').failPlay=false;await ui.element('connect').emit('click');
  assert.equal(ui.connections.length,1);assert.equal(ui.element('audio').srcObject,stream);
  assert.equal(ui.element('audio').playCount,2);assert.equal(ui.element('connect').disabled,true);
});

test('pagehide and hidden visibility do not close or pause active audio',async()=>{
  const ui=receiver(),peer=await ui.connect();await ui.track(peer);
  ui.emit('pagehide');ui.emit('visibilitychange');
  assert.equal(peer.closeCount,0);assert.equal(ui.element('audio').pauseCount,0);
  assert.ok(ui.element('audio').srcObject);
});

test('explicit stop closes peer, pauses audio and releases the server session',async()=>{
  const ui=receiver(),peer=await ui.connect();await ui.track(peer);
  ui.element('stop').emit('click');
  assert.equal(peer.closeCount,1);assert.equal(ui.element('audio').pauseCount,1);
  assert.equal(ui.element('audio').srcObject,null);
  assert.ok(ui.calls.some(call=>call.url==='/api/peers/peer-1'&&call.options.method==='DELETE'));
});

test('returning to a paused page enables gesture-based playback resume',async()=>{
  const ui=receiver(),peer=await ui.connect();await ui.track(peer);
  ui.element('audio').paused=true;ui.emit('pageshow');
  assert.equal(ui.element('connect').disabled,false);assert.equal(peer.closeCount,0);
});


test('brief disconnected state retains playback and recovery cancels reconnect grace',async()=>{
  const ui=receiver(),peer=await ui.connect();await ui.track(peer);
  peer.connectionState='disconnected';peer.onconnectionstatechange();
  assert.equal(peer.closeCount,0);assert.ok(ui.element('audio').srcObject);
  assert.ok([...ui.timers.values()].some(timer=>timer.delay===10000));
  peer.connectionState='connected';peer.onconnectionstatechange();
  assert.equal(peer.closeCount,0);assert.equal(ui.timers.size,0);
});
