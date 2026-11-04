# AirEar

AirEar streams Windows system audio to a phone browser over your private Wi-Fi. Keep one pair of earphones connected to your phone and listen to PC audio in a café, library, or another nearby place without switching the earphones between devices.

[한국어 README](README.ko.md) · [Install guide](docs/INSTALL.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Language files](docs/LANGUAGES.md)

## How it works

```text
Windows system audio → Electron loopback capture → WebRTC/Opus → phone browser
```

The phone needs no app installation. Open the LAN address in Safari, Chrome, or another modern mobile browser, enter the PIN shown by AirEar, and tap **Connect and listen**. Bluetooth earphones such as AirPods stay paired to the phone.

## Install

1. Download the latest **AirEar-Setup-x64.exe** from [GitHub Releases](https://github.com/mycodehive/airear/releases).
2. Run the per-user installer. It does not require administrator rights by default.
3. Start AirEar. Windows SmartScreen may warn because the installer is currently unsigned.
4. The app checks GitHub Releases on startup and every four hours. Updates download only after you choose the update button.

The Electron installer is a new installation format. To move from the old Python `AirEar.exe`, close that app and run the new setup program once. Existing settings in `%LOCALAPPDATA%\AirEar\settings.json` are read where their fields still apply.

## Connect a phone

1. Connect the PC and phone to the same trusted Wi-Fi network.
2. In AirEar, choose an output device. **Start broadcasting** automatically selects `CABLE Input (VB-Audio Virtual Cable)` when it is available; otherwise, the selected or default output device is used.
3. Scan the QR code or open the displayed LAN address on the phone.
4. Enter the 8-digit PIN from the desktop app and tap **Connect and listen**.
5. Adjust listening volume with the phone's volume buttons. Use AirEar's slider to change the stream gain.

To keep audio off the PC speakers, install VB-CABLE from the [official VB-Audio website](https://vb-audio.com/Cable/) and route Windows playback to `CABLE Input` in Windows Sound settings. AirEar captures that endpoint and streams it to connected phones. AirEar does not silently download or install audio drivers. See [installation notes](docs/INSTALL.md).

## Current capture scope

On Windows, AirEar enumerates render endpoints that support WASAPI loopback and captures the selected endpoint. The broadcast button prefers `CABLE Input (VB-Audio Virtual Cable)` automatically when available. Windows playback must be routed to that endpoint for its loopback signal to contain the desired audio. Selecting an endpoint in AirEar chooses the capture source; it does not change Windows' global playback routing.

The receiver uses a native HTML audio element after a user tap. Screen-lock playback still depends on the phone OS and browser; it is not guaranteed. Current audio capture and long-duration behavior need validation on physical Windows hardware.

## Languages

Korean, English, and Japanese JSON language files live in `%LOCALAPPDATA%\AirEar\languages`. AirEar creates them from the bundled defaults on first launch. Edit the JSON values and the desktop UI reloads them automatically; the phone page reloads its selected language file while open. See [docs/LANGUAGES.md](docs/LANGUAGES.md) to add another language.

## Development

- HTML/CSS: desktop and phone screens
- JavaScript: app logic, signalling, WebRTC, settings, and language loading
- Electron 45 + Node.js 24: desktop runtime
- `node-cpal`: WASAPI output-device enumeration and endpoint-specific loopback capture
- Express + WebSocket: LAN-only signalling and phone page
- `electron-builder` + NSIS: per-user x64 installer
- GitHub Actions: lint, tests, Windows installer build, install/launch smoke test, checksum

```sh
npm ci
npm run lint
npm test
npm start
```

The Windows installer is built on Windows with `npm run dist:win`. See [development](docs/DEVELOPMENT.md) and [release](docs/RELEASING.md) notes.

## Network and privacy

AirEar binds its signalling server to the local interfaces and accepts private IPv4 LAN clients only. The 8-digit PIN is rate limited. HTTP signalling is not encrypted, so use a trusted private network and do not expose the port to the public internet. WebRTC media is encrypted by DTLS-SRTP, but that does not encrypt the separate HTTP signalling exchange.

## License and signing

The application is currently distributed without a code-signing certificate. Windows SmartScreen can display a warning. Review the source and SHA256 checksums attached to each release before installing.
