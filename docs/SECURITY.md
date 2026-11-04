# Security notes

- Default use is a trusted private LAN. The server binds to `0.0.0.0` but rejects HTTP and WebSocket clients outside RFC1918 IPv4 or loopback.
- Receiver access requires an 8-digit PIN. Failed PIN attempts are limited per remote address. At most four receivers are accepted.
- Signaling messages are size-limited and only forwarded between the authenticated desktop session and PIN-authorized receivers.
- PINs and session tokens are not written to logs. The desktop token is generated per server session and is only returned to the local Electron renderer over restricted IPC.
- The phone signaling page uses HTTP on the LAN. PIN and signaling traffic can be observed by a hostile device on that network. Use trusted Wi-Fi and do not expose the port to the internet.
- WebRTC media uses DTLS-SRTP; this does not encrypt the separate HTTP signaling exchange.
- Electron uses `contextIsolation`, sandboxed renderers, `nodeIntegration: false`, a restrictive content security policy, and narrow preload methods.
- Automatic updates use electron-updater release metadata and package hashes over GitHub HTTPS. No Authenticode certificate is configured, so installer signature verification is disabled and users may see SmartScreen warnings. Review release provenance and checksums.
