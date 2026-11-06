# AirEar v2.0.1

- Electron Windows desktop app with HTML/CSS/JavaScript UI, editable Korean/English/Japanese JSON language packs, tray support and NSIS installation.
- Refresh the LAN URL and QR after network interface/AP changes; clear stale addresses.
- Select a WASAPI output endpoint and request the corresponding Windows default playback device. Prefer VB-CABLE when starting broadcast.
- Restore receiver retry controls when audio broadcasting has not started.

## Install
Download AirEar-Setup-2.0.1-x64.exe and run it. Python v1.x users must close the old app and install this Electron version once; the old Python updater cannot migrate the runtime. Later Electron updates use the app updater.

The installer is unsigned and Windows SmartScreen may warn. SHA256SUMS.txt is included.

Automated validation includes JavaScript checks, 23 Node tests, Windows COM helper compilation, NSIS build and installed-app startup smoke testing. Physical AP switching, actual Windows endpoint switching, phone playback and long-duration streaming remain hardware validation items. Some applications retain explicit per-app output routing. Windows default output switching uses PolicyConfig COM and can fail on unsupported or restricted systems.
