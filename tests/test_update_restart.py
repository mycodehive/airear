"""Regression checks for independently restarting a frozen onefile application."""
from pathlib import Path

import pytest

from airear import updater


def test_restart_environment_discards_old_unpack_state(monkeypatch):
    monkeypatch.setenv('_PYI_APPLICATION_HOME_DIR', r'C:\Temp\_MEIold')
    monkeypatch.setenv('_PYI_PARENT_PROCESS_LEVEL', '1')
    monkeypatch.setenv('_PYI_ARCHIVE_FILE', r'C:\AirEar.exe')
    monkeypatch.setenv('_MEIPASS2', r'C:\Temp\_MEIold')
    monkeypatch.setenv('AIREAR_KEEP', 'ordinary-setting')
    result = updater.restart_environment()
    assert result['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert result['AIREAR_KEEP'] == 'ordinary-setting'
    assert not any(key.startswith('_PYI_') or key == '_MEIPASS2' for key in result)
    # Cleaning the child environment must not modify the running application's env.
    assert updater.os.environ['_PYI_PARENT_PROCESS_LEVEL'] == '1'


def test_replacement_helper_uses_fresh_environment_and_stable_directory(tmp_path, monkeypatch):
    from airear import i18n
    monkeypatch.setattr(i18n, 'tr', lambda value: value)
    target = tmp_path / "user's app" / 'AirEar.exe'
    target.parent.mkdir()
    target.write_bytes(b'MZold')
    staged = tmp_path / 'download' / 'AirEar.exe'
    staged.parent.mkdir()
    staged.write_bytes(b'MZnew')
    calls = []
    monkeypatch.setattr(updater.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(updater.sys, 'platform', 'win32')
    monkeypatch.setattr(updater.sys, 'executable', str(target))
    monkeypatch.setenv('_PYI_APPLICATION_HOME_DIR', 'deleted-temporary-directory')
    monkeypatch.setattr(updater.subprocess, 'Popen', lambda *args, **kwargs: calls.append((args, kwargs)))
    updater.launch_replacement(staged)
    command, options = calls[0]
    assert options['env']['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert '_PYI_APPLICATION_HOME_DIR' not in options['env']
    assert options['cwd'] == str(target.parent)
    assert options['close_fds']
    script = Path(command[0][-1]).read_text(encoding='utf-8-sig')
    assert "user''s app" in script
    assert '-Timeout 120' in script
    assert '[System.IO.File]::Replace($temporary,$target,$backup,$true)' in script
    assert '$attempt -lt 40' in script
    assert "$env:PYINSTALLER_RESET_ENVIRONMENT='1'" in script
    assert '-WorkingDirectory (Split-Path -Parent $target)' in script
    assert 'if ($installed -and' in script
    assert 'RunAs' not in script
    assert target.read_bytes() == b'MZold'  # Helper generation never edits the running EXE.


def test_source_python_cannot_launch_windows_replacement(tmp_path, monkeypatch):
    monkeypatch.setattr(updater.sys, 'frozen', False, raising=False)
    with pytest.raises(RuntimeError):
        updater.launch_replacement(tmp_path / 'AirEar.exe')
