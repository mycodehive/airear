# Install and connect

## Windows installation

1. Download `AirEar-Setup-x64.exe` from the latest GitHub Release.
2. Run the installer. It installs for the current Windows user and does not request administrator rights by default.
3. Windows SmartScreen can show a warning because AirEar is not code signed. Check the release source and SHA256 file before proceeding.
4. Launch AirEar from the Start menu or desktop shortcut.

The Electron installer is not an in-place replacement for the previous Python one-file EXE. Close the old app and run this installer once. Settings are read from `%LOCALAPPDATA%\AirEar\settings.json`; supported theme, language, port, gain and update options carry over.

## Connect a phone

1. Put the Windows PC and phone on the same trusted Wi-Fi network.
2. Select the desired Windows playback output in Windows Sound settings. AirEar currently captures the active system audio mix.
3. In AirEar, start the LAN server and choose **Start broadcasting**. Allow display/audio capture if Windows prompts.
4. Scan the QR code or type the LAN URL in the phone browser.
5. Enter the 8-digit PIN shown in AirEar and tap **Connect and listen**. iOS and Android require this explicit user action for playback.
6. Use the phone's hardware volume buttons for receiver volume. Use the desktop slider for stream gain.

The server listens on the displayed LAN address and port, default `8765`. Allow AirEar on the Windows Private network firewall profile if prompted. Do not create an internet port-forwarding rule.

## Keep PC speakers quiet

Windows system loopback captures the system audio mix; it does not mute the physical speakers by itself. To keep the PC quiet, install VB-CABLE manually from the [official VB-Audio page](https://vb-audio.com/Cable/) and set the virtual `CABLE Input` playback device as the Windows default output. AirEar then captures the mix routed to that default output. Driver installation may need administrator approval or a reboot. AirEar never downloads or launches a driver installer automatically.

## Phone background playback

Tap Play/Listen on the phone before locking the screen. Playback in the background or while locked can still be limited by browser and OS power rules. Return to the browser and press Play again if the phone pauses.
