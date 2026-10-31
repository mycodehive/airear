<p align="center"><img src="src/airear/assets/airear.png" alt="AirEar icon" width="144"></p>

# AirEar

**Your PC's sound. Your phone. One pair of earbuds.**

[한국어 README](README.ko.md)

AirEar sends the sound playing on your Windows PC to a nearby phone's web browser. Keep your earbuds connected to your phone while you work, study, watch a lecture, or listen to a video on your PC. You do not have to disconnect them from your phone and pair them with your PC every time you switch devices.

At a café or library, route Windows sound to a virtual audio device to keep the PC's speakers quiet, then listen through the earbuds already connected to your phone. AirEar runs on Windows; the phone opens a browser page, with no companion app to install.

## How it works

Windows audio → WASAPI loopback → local WebRTC connection → phone browser → phone speaker or connected earbuds.

AirEar uses a local network connection. It supports browser-based receivers rather than a particular phone brand: try a current browser with WebRTC and Web Audio support, such as Safari or Chrome. Actual device and browser compatibility still needs physical-device testing. AirEar does not guarantee that other phone apps, calls, and browser audio will mix or switch seamlessly.

## Install on Windows

Requirements: Windows 10/11 x64 and a phone on the same trusted local network.

1. Open [GitHub Releases](https://github.com/mycodehive/airear/releases) and download `AirEar.exe` when a release is available.
2. For the current development build, open a successful [Windows EXE Actions run](https://github.com/mycodehive/airear/actions), download the `AirEar-x64` artifact, and extract it. A GitHub sign-in may be required to download Actions artifacts.
3. Keep the EXE in a folder you can write to, then run it. **You do not need to install Python.**
4. If you want the PC's speakers to stay quiet, accept the optional VB-CABLE installation prompt and complete the official driver's installer. Administrator approval and a restart may be required. You can choose to install it later and test with a regular output device.

The build includes a SHA256 checksum. In PowerShell, use `Get-FileHash .\AirEar.exe -Algorithm SHA256` and compare the result with `SHA256SUMS.txt`. The app is currently unsigned, so Windows SmartScreen may show a warning.

## Connect your phone

1. Connect the PC and phone to the same network. A trusted personal hotspot is often more practical than shared café Wi-Fi, which may block connections between devices.
2. Connect your earbuds or Bluetooth headphones to **your phone**.
3. Open AirEar and choose the Windows output device to capture. Start the streaming server.
4. If Windows asks about firewall access, allow it for your trusted private network.
5. Scan the QR code with your phone or open the displayed address in its browser.
6. Enter the PIN shown in AirEar, then tap **Start listening**. The tap is required by browser playback policies.
7. Adjust the PC's transmit level in AirEar and the listening level on the phone independently.

Use the tray icon to bring AirEar back after minimizing it. Streaming continues while the window is in the tray. Use the tray's **Quit** command to stop the server and exit.

### Keep the PC speakers quiet

Install [VB-CABLE](https://vb-audio.com/Cable/) using AirEar's consent-based helper or the publisher's official installer. In **Windows Settings → System → Sound → Output**, choose **CABLE Input (VB-Audio Virtual Cable)**. In AirEar, select that device's loopback capture.

If a player or meeting app uses its own output setting, point that app to CABLE Input too. Leave Windows' **Listen to this device** option off. This routes sound through the virtual device instead of the physical PC speakers; it does not rely on muting the Windows master volume.

Choosing a normal speaker loopback will normally play sound on both the PC and phone.

## Languages

English and Korean are included. Select a language in AirEar's settings to change the interface immediately. Language text is stored in separate JSON files so translations can be maintained without changing Python or JavaScript source.

You can add or override language files in `%LOCALAPPDATA%\AirEar\languages`. Saved changes are reloaded while the program is running. See [the language-file guide](docs/LANGUAGES.md) for the JSON format, placeholders, and how to add another language.

## Features

- Default or selected Windows WASAPI loopback device, automatic recovery, and continuous silent frames.
- Opus/WebRTC audio, up to four receivers, per-phone listening volume, and bounded audio buffers.
- QR address, PIN authentication, session expiry, and desktop receiver controls.
- Independent transmit volume from 0–200%, mute, peak limiting, and an input level meter.
- Light, dark, and system themes; scrollable layout; tray operation; runtime language files.
- Optional official VB-CABLE installer helper, AppData settings and logs, and GitHub stable-release update checks.

## Network and playback notes

Use AirEar on a trusted local network. Default HTTP does not encrypt the PIN and signaling credentials; configure HTTPS with a certificate trusted by the phone for regular use. Do not expose the server to the internet or add router port forwarding. [HTTPS and security guide](docs/SECURITY.md).

Phone screen locking, background tabs, battery-saving settings, and browser policies may interrupt playback. Return to the receiver page and tap Start listening if needed. End-to-end latency and long-running playback depend on the actual devices and network; no fixed latency is promised.

## Build and validation

The initial Windows Actions build passed its tests, PyInstaller onefile build, AMD64 PE checks, frozen-EXE smoke test, and checksum generation. This confirms packaging, not physical Windows audio or phone playback. Follow [PR #1](https://github.com/mycodehive/airear/pull/1) and the [validation checklist](docs/VALIDATION.md) for current acceptance status.

For development, install [uv](https://docs.astral.sh/uv/) and run:

```powershell
uv sync --locked --extra dev --python 3.12.14
uv run --locked --extra dev python -m airear
./scripts/build.ps1
```

The locked dependencies include the Python desktop UI, audio engine, web server, receiver assets, and build tools. The EXE bundles the Python runtime; VB-CABLE remains a separately installed driver. Tag workflows publish prereleases until physical-device acceptance is recorded. Automatic updates use stable GitHub Releases.

[Installation details](docs/INSTALL.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Release process](docs/RELEASING.md)
