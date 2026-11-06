'use strict';
const { execFile } = require('node:child_process');
const path = require('node:path');
const { promisify } = require('node:util');
const run = promisify(execFile);
async function setWindowsOutput(deviceId) {
  if (process.platform !== 'win32') throw new Error('Windows output switching requires Windows.');
  const endpoint = String(deviceId).match(/\{0\.0\.0\.\d+\}\.\{[0-9a-f-]{36}\}/i)?.[0];
  if (!endpoint) throw new Error('The selected device has no valid Windows render endpoint ID.');
  // PowerShell requires a real file outside app.asar.
  const script = path.join(__dirname, 'windows', 'set-output.ps1').replace('app.asar'+path.sep, 'app.asar.unpacked'+path.sep);
  await run('powershell.exe', ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script, '-Endpoint', endpoint], { windowsHide: true, timeout: 15000 });
  return true;
}
module.exports = { setWindowsOutput };
