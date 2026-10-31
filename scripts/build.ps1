$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw '개발 빌드에는 uv가 필요합니다. https://docs.astral.sh/uv/getting-started/installation/'
}
uv sync --locked --extra dev --python 3.12.14
if ($LASTEXITCODE) { throw 'Dependency sync failed' }
uv run --locked --extra dev ruff check .
if ($LASTEXITCODE) { throw 'Lint failed' }
uv run --locked --extra dev pytest -q
if ($LASTEXITCODE) { throw 'Tests failed' }
uv run --locked --extra dev python scripts/build_assets.py
uv run --locked --extra dev pyinstaller --noconfirm --clean WindowsAudio_iPhone.spec
if ($LASTEXITCODE) { throw 'Build failed' }
$exe = Join-Path $PWD 'dist/WindowsAudio_iPhone.exe'
$bytes = [System.IO.File]::ReadAllBytes($exe)
if ($bytes[0] -ne 77 -or $bytes[1] -ne 90) { throw 'Invalid DOS header' }
$peOffset = [BitConverter]::ToInt32($bytes, 0x3c)
if ($peOffset -lt 64 -or $peOffset + 26 -ge $bytes.Length) { throw 'Invalid PE offset' }
if ([BitConverter]::ToUInt32($bytes, $peOffset) -ne 0x4550) { throw 'Invalid PE signature' }
if ([BitConverter]::ToUInt16($bytes, $peOffset + 4) -ne 0x8664) { throw 'Executable must be AMD64' }
if ([BitConverter]::ToUInt16($bytes, $peOffset + 24) -ne 0x20b) { throw 'Executable must be PE32+' }
$process = Start-Process -FilePath $exe -ArgumentList '--smoke-test' -PassThru
if (-not $process.WaitForExit(60000)) { $process.Kill(); throw 'EXE smoke test timed out' }
if ($process.ExitCode -ne 0) { throw 'EXE smoke test failed' }
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
[System.IO.File]::WriteAllText((Join-Path $PWD 'dist/SHA256SUMS.txt'), "$hash  WindowsAudio_iPhone.exe`n")
