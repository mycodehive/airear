# Releasing

The Windows workflow runs on pull requests and feature pushes. It runs syntax checks, Node tests, builds an NSIS x64 installer, installs it silently on the Windows runner, verifies the installed executable is x64 PE, runs the app's smoke mode, and uploads the installer plus `latest.yml`, blockmap, and SHA256 checksums.

To publish a stable version:

1. Update `package.json` version and regenerate `package-lock.json` with `npm install --package-lock-only`.
2. Update `docs/RELEASE_NOTES.md` with user-visible changes and known limitations.
3. Merge the change. A `vX.Y.Z` tag or a `main` commit whose first line is `release: vX.Y.Z` triggers the release job.
4. The job requires the version in the tag/commit message to match `package.json`. It publishes the NSIS setup, `latest.yml`, blockmap, and SHA256 file to a non-draft GitHub Release.

The application checks GitHub Releases at startup and every four hours. It asks before downloading, shows download progress, verifies the update using the signed release metadata's package hash over HTTPS, and offers restart/install when complete. The Windows installer is currently unsigned; SmartScreen warnings are expected. Because no code-signing certificate is configured, Authenticode verification is explicitly disabled in electron-builder; release hashes and GitHub's HTTPS release channel are used instead.

The Python v1.x and Electron v2.x installers are different products for update purposes. Existing Python users must install the first Electron version once manually. Keep the app ID and `%LOCALAPPDATA%\AirEar` path stable so user settings remain available.

## Release verification checklist

- Confirm Windows Actions build, automated tests, install smoke, and artifacts all pass.
- Confirm the release is public, not a draft or prerelease, and includes setup, `latest.yml`, blockmap, and checksums.
- Confirm the installer is a Windows x64 installer and the installed `AirEar.exe` is PE32+ AMD64.
- Run the capture checklist in `VALIDATION.md` on physical Windows and phone hardware before claiming end-to-end support.
