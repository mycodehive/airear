# Validation status and hardware checklist

## Automated checks

GitHub Actions is configured to run `npm run lint`, `npm test`, build the NSIS x64 installer, install it silently on a Windows runner, verify the installed `AirEar.exe` PE architecture, and launch its smoke-test mode. The CI result for each change is the source of truth; do not mark a run passed based on configuration alone.

## Not verified by CI

The GitHub runner does not represent the user's physical audio endpoints or phone. Before calling the Electron migration production-ready, record these observations on a Windows 10/11 PC and real phone:

- System audio is captured from the intended Windows default output, including VB-CABLE.
- PC speakers remain quiet when Windows output is routed to VB-CABLE.
- Audio continues through silence, device changes, disconnect/reconnect, and a 30-minute stream.
- Multiple phone browsers connect and clean up correctly.
- Safari/Chrome playback, AirPods, screen lock, and background return are recorded separately by OS/browser version.
- LAN address selection uses the reachable active private adapter, not VPN or public addresses.
- Firewall behavior and 100%, 125%, 150%, and 200% DPI are checked.

Current implementation is a JavaScript/Electron loopback baseline. Arbitrary endpoint selection and automatic WASAPI endpoint recovery are not implemented in this baseline. Do not mark them verified.
