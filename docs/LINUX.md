# AirEar 2.0.2 for Linux (x86-64)

Linux-specific packaging and audio integration extend the 2.0.2 source without replacing the existing Windows assets or tag. LINUX-BUILD.txt records the exact source commit. Packages target Ubuntu 24.04 x64; other distributions are not validated.

## Install

Download `AirEar-2.0.2-linux-x64.deb` and run:

```sh
sudo apt install ./AirEar-2.0.2-linux-x64.deb
```

Alternatively, install `pulseaudio-utils`, download the AppImage, make it executable and run it. AppImage requires your distribution's FUSE support; Ubuntu 24.04 may need `libfuse2t64`. The AppImage does not include a sound server.

```sh
chmod +x AirEar-2.0.2-linux-x64.AppImage
./AirEar-2.0.2-linux-x64.AppImage
```

Run as your normal desktop user. PulseAudio or PipeWire with `pipewire-pulse` must be available. The Debian package installs the `pactl`/`parec` tools through `pulseaudio-utils`. Settings and languages use Electron's Linux user-data directory, normally `~/.config/airear` (or `$XDG_CONFIG_HOME/airear`).

## Listen from a phone

Put the PC and phone on the same trusted LAN. Select a Linux output device and start broadcast. Open the shown URL/QR on your phone, enter the PIN, then tap Connect and listen. Allow TCP 8765 (or the configured signalling port) and WebRTC UDP traffic only on your trusted network as needed.

Linux captures the selected sink's monitor with `parec`. VB-CABLE and Windows playback policy are not used. Selecting a device changes the default sink for new playback streams. Existing applications may retain their own output route; adjust them in system sound settings or pavucontrol. For a silent PC, create/select a virtual sink and route applications there; muting physical output may also affect its monitor capture.

On Linux, close exits the app and minimize uses the normal window manager; tray hiding is disabled. Automatic Linux updates are not configured in this first Linux build; install new packages from Releases. Screen-lock phone audio and physical devices still need device testing.

## Validation

CI runs syntax/unit tests, generates audio into a PulseAudio virtual sink and checks monitor samples, builds AppImage/deb, inspects the ELF/deb and launches the packaged app in smoke mode under Xvfb. This does not validate physical audio hardware, Wayland/X11 interaction, Bluetooth, phone playback or long-running streams. Check SHA256SUMS-linux.txt before installation.
