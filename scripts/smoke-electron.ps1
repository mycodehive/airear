$ErrorActionPreference = 'Stop'
$installer = Get-ChildItem 'dist-electron/AirEar-Setup-*-x64.exe' | Select-Object -First 1
if (-not $installer) { throw 'NSIS installer was not produced.' }
$target = Join-Path $env:RUNNER_TEMP 'AirEar-Install-Smoke'
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Start-Process -FilePath $installer.FullName -ArgumentList @('/S', "/D=$target") -Wait
$exe = Join-Path $target 'AirEar.exe'
if (-not (Test-Path $exe)) { throw 'Installed AirEar.exe is missing.' }
$stream = [System.IO.File]::OpenRead($exe)
try {
    $reader = [System.IO.BinaryReader]::new($stream)
    if ($reader.ReadUInt16() -ne 0x5A4D) { throw 'The installed app does not have an MZ executable header.' }
    $stream.Position = 0x3C
    $peOffset = $reader.ReadInt32()
    $stream.Position = $peOffset
    if ($reader.ReadUInt32() -ne 0x00004550) { throw 'The installed app does not have a PE header.' }
    if ($reader.ReadUInt16() -ne 0x8664) { throw 'The installed app is not an x64 Windows executable.' }
} finally { $stream.Dispose() }
$process = Start-Process -FilePath $exe -ArgumentList '--smoke-test' -PassThru -Wait
if ($process.ExitCode -ne 0) { throw "Installed app smoke test exited with code $($process.ExitCode)." }
$hashLines = Get-ChildItem 'dist-electron' -File | Where-Object { $_.Name -match '^AirEar-Setup-.*-x64\.exe$|^latest\.yml$|\.blockmap$' } | Sort-Object Name | ForEach-Object {
    $hash = Get-FileHash $_.FullName -Algorithm SHA256
    "$($hash.Hash)  $($_.Name)"
}
$hashLines | Set-Content 'dist-electron/SHA256SUMS.txt' -Encoding ascii
