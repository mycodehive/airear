# Troubleshooting

## The phone cannot open the address

- Check that the PC and phone use the same Wi-Fi and are not on guest Wi-Fi with client isolation.
- Use the private LAN address displayed by AirEar. A VPN or multiple adapters can change which LAN is reachable.
- If you changed Wi-Fi access points and the displayed address is stale, press **Refresh IP**. This clears the old value and looks up the current active Windows network route.
- Allow AirEar on the Windows Private network firewall profile. Keep the port closed to public networks.
- Confirm the LAN server is running and the selected port is not already in use.

## The PIN is rejected

Enter the current 8-digit PIN shown in the desktop app. Stop and restart the LAN server to generate a new PIN. PIN attempts are rate limited.

## No audio reaches the phone

- Start broadcasting from the desktop app after starting the LAN server.
- Select the expected endpoint in AirEar and confirm it supports loopback. Start broadcasting automatically prefers VB-CABLE when available.
- If using VB-CABLE, route Windows playback to `CABLE Input` in Windows Sound settings. AirEar's selector changes the capture endpoint only; it does not change the Windows playback route.
- Check the desktop audio level meter and make sure stream mute is off.
- In the phone browser, tap Connect and listen, then tap the native audio player's Play button if requested.
- Some apps use protected audio that Windows loopback may not capture.

## Keep PC speakers quiet

Route Windows playback to the VB-CABLE virtual `CABLE Input` endpoint. Driver setup is manual from the official VB-Audio site; Windows may require administrator approval and a reboot. A failed or skipped driver installation does not prevent testing with a normal output device.

## Audio pauses when the phone is locked

Background and lock-screen playback are controlled by the phone OS and browser. Return to the browser and tap Play again. AirEar does not promise uninterrupted screen-off playback on every device.

## Updates

Python v1.x cannot be replaced by the Electron updater. Install the Electron NSIS setup once. Later Electron updates download through the app after you choose the update action. If update installation fails, download the latest setup from GitHub Releases and run it over the existing per-user installation.
