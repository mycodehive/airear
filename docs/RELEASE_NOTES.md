# AirEar v2.0.2

- Show “세팅중입니다. 잠시만 기다려주세요.” while initializing; remove it after setup and report initialization failures.
- Run Windows network discovery asynchronously so it does not block desktop/signalling work. Start the LAN listener without waiting for route discovery.
- Query audio devices and network information concurrently. Load the native audio binding on demand and remove repeated per-device configuration probes.
- Skip the Windows playback switch helper when the requested endpoint is already the default. Prevent duplicate broadcast starts.
- Hide empty QR images; generate QR codes after broadcast startup and hide them again when broadcast stops.

Validation: JavaScript syntax checks and 24 Node tests, including delayed asynchronous Windows route discovery. Windows CI compiles COM interop, builds NSIS and smoke-tests installed startup. Exact startup/broadcast time improvements have not been measured on physical Windows/phone hardware.

Install AirEar-Setup-2.0.2-x64.exe. Python v1.x users must install the Electron setup once. The installer is unsigned and may trigger SmartScreen. SHA256SUMS.txt is included.
