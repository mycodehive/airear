'use strict';

const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, desktopCapturer, session, dialog, shell, clipboard } = require('electron');
const { autoUpdater } = require('electron-updater');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const QRCode = require('qrcode');
const { AirEarServer, getActiveLanAddresses } = require('./server.cjs');
const { readLanguagePack, repairLanguageFiles } = require('./i18n.cjs');
const { AudioCaptureService } = require('./audio.cjs');

const APP_NAME = 'AirEar';
const VERSION = app.getVersion();
const localData = process.env.LOCALAPPDATA || path.join(app.getPath('home'), 'AppData', 'Local');
const dataRoot = path.join(localData, APP_NAME);
app.setPath('userData', dataRoot);
const languageRoot = path.join(dataRoot, 'languages');
const logsRoot = path.join(dataRoot, 'logs');
const logFile = path.join(logsRoot, 'airear.log');
const languageDefaults = app.isPackaged ? path.join(process.resourcesPath, 'languages') : path.join(__dirname, '..', 'languages');

fs.mkdirSync(languageRoot, { recursive: true });
fs.mkdirSync(logsRoot, { recursive: true });
repairLanguageFiles({ userRoot: languageRoot, bundledRoot: languageDefaults });

function log(level, message) {
  const line = `${new Date().toISOString()} [${level}] ${message}\n`;
  try { fs.appendFileSync(logFile, line, 'utf8'); } catch { /* logging must not stop the service */ }
}

function loadSettings() {
  const defaults = { port: 8765, theme: 'system', language: 'ko', gain: 1, muted: false, autoStart: false, checkUpdates: true };
  try {
    const loaded = JSON.parse(fs.readFileSync(path.join(dataRoot, 'settings.json'), 'utf8'));
    return {
      ...defaults,
      ...loaded,
      autoStart: loaded.autoStart ?? loaded.auto_start ?? defaults.autoStart,
      checkUpdates: loaded.checkUpdates ?? loaded.check_updates ?? defaults.checkUpdates,
      port: Number(loaded.port) >= 1024 && Number(loaded.port) <= 65535 ? Number(loaded.port) : defaults.port,
    };
  } catch { return defaults; }
}

let settings = loadSettings();
let mainWindow = null;
let tray = null;
let quitting = false;
let service = null;
let serverState = null;
let updaterAvailable = false;
let shutdownStarted = false;
const instanceLock = app.requestSingleInstanceLock();
const audioCapture = new AudioCaptureService({
  onFrame: frame => send('audio-frame', frame),
  onError: error => {
    log('error', `WASAPI loopback capture failed: ${error?.name || 'Error'}`);
    send('audio-error', { message: String(error?.message || error || 'Audio capture failed') });
  },
});

function saveSettings(next) {
  settings = { ...settings, ...next };
  const target = path.join(dataRoot, 'settings.json');
  const temporary = `${target}.tmp`;
  fs.writeFileSync(temporary, JSON.stringify(settings, null, 2), 'utf8');
  fs.renameSync(temporary, target);
  return settings;
}

function send(channel, data) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, data);
}

function iconPath() {
  return app.isPackaged ? path.join(process.resourcesPath, 'airear.ico') : path.join(__dirname, '..', 'src', 'airear', 'assets', 'airear.ico');
}

function showWindow() {
  if (!mainWindow) createWindow();
  mainWindow.show();
  mainWindow.focus();
}

function createTray() {
  if (tray) return;
  let icon = nativeImage.createFromPath(iconPath());
  if (icon.isEmpty()) icon = nativeImage.createEmpty();
  tray = new Tray(icon);
  tray.setToolTip(`${APP_NAME} ${VERSION}`);
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'AirEar 열기', click: showWindow },
    { type: 'separator' },
    { label: '종료', click: () => { quitting = true; app.quit(); } },
  ]));
  tray.on('double-click', showWindow);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1040, height: 760, minWidth: 760, minHeight: 560,
    show: false, title: `${APP_NAME} ${VERSION}`,
    icon: iconPath(),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'desktop', 'index.html'));
  mainWindow.once('ready-to-show', () => mainWindow?.show());
  mainWindow.on('minimize', event => { event.preventDefault(); mainWindow.hide(); createTray(); });
  mainWindow.on('close', event => {
    if (!quitting) { event.preventDefault(); mainWindow.hide(); createTray(); }
  });
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
}

async function startServer() {
  if (!service) {
    service = new AirEarServer({
      phoneRoot: path.join(__dirname, 'phone'), languageRoot, bundledLanguageRoot: languageDefaults,
      onChange: state => { serverState = state; send('server-state', state); },
    });
  }
  serverState = await service.start(settings.port);
  log('info', `LAN signaling service started on port ${serverState.port}`);
  return { ...serverState, desktopToken: service.desktopToken };
}

async function stopServer() {
  if (!service) return { running: false };
  await service.stop();
  serverState = service.snapshot();
  send('server-state', serverState);
  log('info', 'LAN signaling service stopped');
  return serverState;
}

async function checkForUpdates(silent = true) {
  if (!app.isPackaged || !settings.checkUpdates) return { supported: false };
  try {
    const result = await autoUpdater.checkForUpdates();
    const version = result?.updateInfo?.version || '';
    return { supported: true, update: !!version && version !== VERSION, version };
  } catch (error) {
    log('warn', `Update check failed: ${error.name || 'Error'}`);
    if (!silent) dialog.showMessageBox(mainWindow, { type: 'warning', message: '업데이트를 확인하지 못했습니다.', detail: '인터넷 연결을 확인한 뒤 다시 시도하세요.', buttons: ['확인'] });
    return { supported: true, update: false, error: true };
  }
}

function configureCapture() {
  session.defaultSession.setPermissionCheckHandler((webContents, permission) => permission !== 'display-capture' || webContents === mainWindow?.webContents);
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    callback(permission === 'display-capture' && webContents === mainWindow?.webContents);
  });
  session.defaultSession.setDisplayMediaRequestHandler(async (request, callback) => {
    if (request.frame?.url && !request.frame.url.startsWith('file://')) return callback(null);
    try {
      const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: 1, height: 1 } });
      if (!sources.length) return callback(null);
      callback({ video: sources[0], audio: 'loopback' });
    } catch (error) {
      log('error', `System loopback capture request failed: ${error.name || 'Error'}`);
      callback(null);
    }
  });
}

ipcMain.handle('app:get-state', () => ({ version: VERSION, settings, server: service?.snapshot() || { running: false }, packaged: app.isPackaged }));
ipcMain.handle('app:save-settings', (_event, next) => saveSettings(next));
ipcMain.handle('network:refresh-addresses', () => service ? service.refreshAddresses() : getActiveLanAddresses());
ipcMain.handle('server:start', async () => startServer());
ipcMain.handle('server:stop', async () => stopServer());
ipcMain.handle('server:desktop-session', () => {
  if (!service?.httpServer) throw new Error('Server is not running');
  return { port: service.port, token: service.desktopToken };
});
ipcMain.handle('qr:create', (_event, text) => QRCode.toDataURL(String(text), { width: 240, margin: 2, errorCorrectionLevel: 'M' }));
ipcMain.handle('audio:list-devices', () => audioCapture.listOutputDevices());
ipcMain.handle('audio:prepare', (_event, deviceId) => audioCapture.prepare(String(deviceId || '')));
ipcMain.handle('audio:start', () => audioCapture.start());
ipcMain.handle('audio:stop', async () => { await audioCapture.stop(); return true; });
ipcMain.handle('language:read', (_event, language) => {
  return readLanguagePack(language, { userRoot: languageRoot, bundledRoot: languageDefaults });
});
ipcMain.handle('app:copy', (_event, text) => { clipboard.writeText(String(text)); return true; });
ipcMain.handle('app:open-log', () => shell.openPath(logFile));
ipcMain.handle('app:check-updates', () => checkForUpdates(false));
ipcMain.handle('app:download-update', async () => {
  if (!app.isPackaged || !updaterAvailable) return { ok: false };
  await autoUpdater.downloadUpdate();
  return { ok: true };
});
ipcMain.handle('app:install-update', () => { autoUpdater.quitAndInstall(); });
ipcMain.handle('app:quit', () => { quitting = true; app.quit(); });

autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = true;
autoUpdater.on('update-available', info => { updaterAvailable = true; send('update-state', { state: 'available', version: info.version }); });
autoUpdater.on('update-not-available', () => { updaterAvailable = false; send('update-state', { state: 'none' }); });
autoUpdater.on('download-progress', progress => send('update-state', { state: 'downloading', percent: Math.floor(progress.percent || 0) }));
autoUpdater.on('update-downloaded', info => send('update-state', { state: 'downloaded', version: info.version }));
autoUpdater.on('error', error => { log('warn', `Update operation failed: ${error.name || 'Error'}`); send('update-state', { state: 'error' }); });

app.on('second-instance', () => showWindow());
app.on('before-quit', event => {
  quitting = true;
  if (!shutdownStarted && (service?.httpServer || audioCapture.stream)) {
    event.preventDefault();
    shutdownStarted = true;
    const runningService = service;
    service = null;
    Promise.allSettled([runningService?.stop(), audioCapture.stop()])
      .then(results => results.filter(result => result.status === 'rejected').forEach(result => log('warn', `Shutdown failed: ${result.reason?.name || 'Error'}`)))
      .finally(() => app.quit());
  }
});
app.whenReady().then(async () => {
  if (!instanceLock) return app.quit();
  if (process.argv.includes('--smoke-test')) return app.quit();
  configureCapture();
  createWindow();
  if (settings.autoStart) startServer().catch(error => log('error', `Auto-start failed: ${error.name || 'Error'}`));
  if (app.isPackaged && settings.checkUpdates) {
    checkForUpdates(true);
    setInterval(() => checkForUpdates(true), 4 * 60 * 60 * 1000).unref();
  }
  app.on('activate', showWindow);
});
app.on('window-all-closed', () => { /* tray app stays resident */ });
app.on('will-quit', () => { try { tray?.destroy(); } catch { /* already disposed */ } });

