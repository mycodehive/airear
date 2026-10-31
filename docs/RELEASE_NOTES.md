# AirEar v1.0.2

- Create editable **ko.json** and **en.json** automatically in `%LOCALAPPDATA%\AirEar\languages`. Desktop and phone interfaces read these external files; existing user edits are preserved.
- Reduce the default window to **840 × 720 logical pixels**, matching a compact desktop layout while retaining scrolling.
- Replace the LAN address dropdown with a text field, preventing accidental mouse-wheel address changes.
- Update checks run when the app starts and every four hours when enabled. New stable versions prompt the user.

The native phone playback and audio smoothing from v1.0.1 remain included.

Download **AirEar.exe** and run it without installing Python, or use the app's update check. Close the existing app before manually replacing the EXE. SHA256SUMS.txt is included for integrity verification.

The EXE is unsigned and Windows SmartScreen may show a warning. Actual device/browser screen-lock playback and end-to-end latency still depend on the environment.
