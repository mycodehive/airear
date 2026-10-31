# AirEar v1.0.0

Listen to Windows PC audio through your phone browser and the earphones already connected to your phone. No phone app or separate Python installation is required.

## Download and start

1. Download **AirEar.exe** and run it on Windows 10/11 x64.
2. Select your audio output device and start streaming.
3. On a phone connected to the same trusted LAN, open the QR address, enter the PIN, and tap Connect and listen.
4. For quiet PC speakers, install optional VB-CABLE and set Windows output and AirEar capture to CABLE Input.

## Included

- WASAPI loopback and Opus/WebRTC audio, up to four receivers.
- Improved FIFO buffering to absorb short capture/encoding stalls.
- Independent volume, QR/PIN authentication and receiver diagnostics.
- English/Korean live JSON languages, light/dark themes, tray operation.
- Official manual VB-CABLE installation guide when automatic setup cannot finish.
- GitHub stable-release update checks.

## Validation and known limits

60 automated tests passed locally. Windows CI runs static analysis, tests, PyInstaller onefile packaging, AMD64 PE checks, a frozen EXE smoke test, and SHA256 generation before publishing. This is the first stable release, authorized after user playback feedback. A complete physical-device compatibility matrix, 30-minute endurance test, and end-to-end latency measurements have not been recorded.

The EXE is unsigned; Windows SmartScreen may show a warning. Verify the download using SHA256SUMS.txt. VB-CABLE is a separate optional driver from VB-Audio and may require administrator permission and a reboot.

Use a trusted LAN. Default HTTP signaling exposes authentication information to that network; see the HTTPS guide for regular use. Public Wi-Fi may isolate devices. Mobile screen locking/background policies may interrupt playback. Internet exposure and fixed latency guarantees are not supported.

[English guide](https://github.com/mycodehive/airear#readme) · [한국어 안내](https://github.com/mycodehive/airear/blob/main/README.ko.md)
