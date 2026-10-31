# Release process

Stable release publication is explicitly authorized by the maintainer. Version numbers must match pyproject.toml, src/airear/__init__.py, GUI/diagnostics labels and scripts/version_info.txt; regenerate uv.lock when changing the project version.

- Push a tag such as v1.0.0, or push a main commit with the first line `release: v1.0.0`.
- Windows CI runs lint, tests, onefile packaging, AMD64 PE checks, frozen smoke execution and checksum generation.
- Only after the build succeeds, the release job uploads AirEar.exe, SHA256SUMS.txt and release notes. A release commit creates the tag at the exact built commit.
- Versions containing a suffix such as -rc.1 publish as prereleases; ordinary versions publish as stable/latest.
- Existing published versions are skipped to avoid silently replacing assets. Publish fixes under a new version.
- Ordinary main commits build artifacts without publishing a release.

Record actual device observations separately from automation in VALIDATION.md. Stable publication does not turn unperformed hardware checks into verified tests. The first v1.0.0 stable release was authorized after user playback feedback; complete endurance and compatibility testing remains pending.

The application updater reads GitHub stable/latest releases and checks the EXE against SHA256SUMS.txt before replacement. Keep the same AirEar.exe asset name across versions.
