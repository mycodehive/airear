# AirEar v1.0.3

- Reset inherited PyInstaller onefile environment before restarting after updates, so the new EXE extracts and uses its own Python runtime instead of a removed previous _MEI directory.
- Wait for shutdown and retry replacement while the old onefile launcher releases its file lock; preserve a backup and restore it if replacement fails.
- Show download percentage on the update button, followed by verification status. Disable the button while checking/downloading and restore it on cancellation or failure.
- Verify expected download length as well as SHA256 before replacement.

**If updating from an older version produces a Python DLL error:** close AirEar, download AirEar.exe from this release manually, replace the old file, and launch it directly. The old updater cannot acquire the restart fix until this version is installed. No separate Python installation is needed.

Windows CI verifies packaging and unit regressions; real Windows in-place self-update still requires device confirmation. The unsigned EXE may trigger SmartScreen.
