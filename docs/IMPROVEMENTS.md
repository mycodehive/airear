# Network and Windows output improvements

AirEar keeps its HTML/CSS, JavaScript/Node.js, Electron, JSON language packs and electron-builder/NSIS architecture.

- Watch interface address changes every three seconds. Refresh the active LAN address and QR after an AP/DHCP change. A missing address remains empty rather than repopulating an old interface address.
- Selecting an output endpoint now requests a Windows default playback endpoint change for console, multimedia and communications roles. Broadcast start applies the preferred VB-CABLE endpoint before starting capture. Explicitly routed applications may retain their own Windows app-volume routing.
- If selection changes during broadcast, stop the previous capture so the selector cannot silently describe another active capture source. Start broadcast again after selection.
- The Windows helper uses PolicyConfig COM interop, an undocumented Windows interface. Failures are reported instead of claiming a successful switch. Unsupported endpoint ID formats are rejected. The helper is bundled outside ASAR and does not install a driver or require permanent elevation.

Validation: Node tests cover existing LAN filtering, receiver lifecycle, language packs, QR and audio normalization. Windows CI additionally compiles the COM interop and builds/installs the NSIS application. Actual AP switching, default playback changes, VB-CABLE sound, phone audio and long-duration streaming require Windows/phone hardware and are not verified by those automated checks.
