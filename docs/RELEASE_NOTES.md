# AirEar v1.0.1

## Playback fix

- Restore direct HTML audio playback (`audio.srcObject` + `audio.play()`) used by the earlier v1.3 receiver, replacing the Web Audio/AudioContext output path.
- Do not explicitly disconnect on pagehide or background transitions.
- Keep the received stream available when autoplay is blocked so a tap can retry playback without reconnecting.
- Allow a short grace period for transient peer disconnections.
- Use phone volume buttons and native player controls for listening volume. The PC transmit gain remains independent.
- Retain the v1.0.0 capture FIFO, prebuffering, bounded receiver queues, and network statistics.

Download **AirEar.exe**, close the previous app, and replace it. Refresh the phone receiver page after restarting the PC app so the new playback code loads. Automatic update checks can discover this stable version.

The earlier v1.3 receiver kept playing with the screen locked on the user's phone. This release restores that playback path; screen-lock behavior on this new build has not yet been physically verified. No universal background-playback guarantee is made.

Windows CI runs Python/JavaScript regression tests, lint, onefile packaging, AMD64 PE checks, frozen EXE smoke execution and SHA256 generation before publishing.

The EXE is unsigned; SmartScreen may show a warning. Python is bundled. Optional VB-CABLE installation and trusted-LAN/HTTPS guidance remain unchanged.
