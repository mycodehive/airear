from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root = Path(SPECPATH)
datas, binaries, hiddenimports = [], [], []
for name in ['aiortc', 'av', 'pyaudiowpatch']:
    d, b, h = collect_all(name)
    datas += d
    binaries += b
    hiddenimports += h
datas += [(str(root / 'src/airear/languages'), 'airear/languages')]
datas += [(str(root / 'src/airear/web'), 'airear/web'), (str(root / 'src/airear/assets'), 'airear/assets')]
a = Analysis([str(root / 'scripts/launcher.py')], pathex=[str(root / 'src')],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='WindowsAudio_iPhone', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / 'src/airear/assets/airear.ico'),
          version=str(root / 'scripts/version_info.txt'), uac_admin=False)
