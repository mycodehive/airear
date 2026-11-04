'use strict';

const { contextBridge, ipcRenderer } = require('electron');

function subscribe(channel, callback) {
  const listener = (_event, value) => callback(value);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
}

contextBridge.exposeInMainWorld('airEar', Object.freeze({
  getState: () => ipcRenderer.invoke('app:get-state'),
  saveSettings: value => ipcRenderer.invoke('app:save-settings', value),
  startServer: () => ipcRenderer.invoke('server:start'),
  stopServer: () => ipcRenderer.invoke('server:stop'),
  getDesktopSession: () => ipcRenderer.invoke('server:desktop-session'),
  listAudioDevices: () => ipcRenderer.invoke('audio:list-devices'),
  prepareAudioCapture: deviceId => ipcRenderer.invoke('audio:prepare', deviceId),
  startAudioCapture: () => ipcRenderer.invoke('audio:start'),
  stopAudioCapture: () => ipcRenderer.invoke('audio:stop'),
  createQr: value => ipcRenderer.invoke('qr:create', value),
  readLanguage: value => ipcRenderer.invoke('language:read', value),
  copy: value => ipcRenderer.invoke('app:copy', value),
  openLog: () => ipcRenderer.invoke('app:open-log'),
  checkUpdates: () => ipcRenderer.invoke('app:check-updates'),
  downloadUpdate: () => ipcRenderer.invoke('app:download-update'),
  installUpdate: () => ipcRenderer.invoke('app:install-update'),
  quit: () => ipcRenderer.invoke('app:quit'),
  onServerState: callback => subscribe('server-state', callback),
  onAudioFrame: callback => subscribe('audio-frame', callback),
  onAudioError: callback => subscribe('audio-error', callback),
  onUpdateState: callback => subscribe('update-state', callback),
}));
