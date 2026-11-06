# Development

## Stack

- HTML/CSS desktop and phone screens
- JavaScript for UI logic, WebRTC, signaling, settings, and translations
- Electron 45.2.2 / Node.js 24.22.2
- `node-cpal` WASAPI output endpoint enumeration and selected endpoint loopback capture
- Express + WebSocket signaling, QR generation with `qrcode`
- `electron-builder` + NSIS per-user x64 installer

## Setup

Install Node.js 24.22.2, then run:

```sh
npm ci
npm run lint
npm test
npm start
```

The phone page is available only after starting the server in the desktop app. Desktop and phone language defaults are in `languages/`; edits in the user's AppData folder are hot-reloaded.

Build the Windows installer on Windows:

```powershell
npm run dist:win
```

Output goes to `dist-electron/`. GitHub Actions additionally performs a silent per-user install, verifies that the installed executable is x64 PE, launches the frozen app smoke mode, and writes SHA256 checksums.

## Process model

- Electron main process: tray/window lifecycle, per-user AppData, updater, permissions, server lifecycle.
- Main process: enumerates render endpoints and captures the selected endpoint with WASAPI loopback. The desktop renderer applies gain/limiting and publishes one WebRTC audio track per phone.
- Node LAN server: serves the phone page, validates private LAN addresses and PIN attempts, and relays signaling messages only.
- Phone browser: negotiates a receive-only peer and plays the received stream through the native `<audio>` element after the user taps Connect.

The renderer runs with context isolation, sandboxing, and Node integration disabled. Only narrow preload IPC methods are exposed.

## Audio scope

AirEar uses `node-cpal` to enumerate Windows render endpoints that support WASAPI loopback and captures the selected endpoint. The broadcast action prefers VB-CABLE when available. Physical Windows hardware testing is still required to validate device compatibility and long-running capture behavior.
