# AirEar v1.0.4

- Detect the phone connection address from active local network interfaces and use only RFC1918 private IPv4 addresses.
- Filter hostname lookup results so public addresses such as 164.x cannot become the default connection address.
- Prefer 192.168.x.x addresses and ignore stale saved addresses when initializing the current LAN address.

The Windows GitHub Actions build runs the automated tests and frozen EXE smoke check. Physical network adapter behavior should still be confirmed on a Windows PC. The EXE is unsigned and may trigger a Windows SmartScreen warning.
