import io
import json
import zipfile

import pytest

from airear import installer, settings, updater
from airear.downloads import validate_url


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_installer_discovers_official_link_without_guessing():
    page = '<a href="https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip">Windows</a>'
    assert installer.discover_package(page).endswith('Pack45.zip')
    with pytest.raises(ValueError):
        installer.discover_package('<a href="https://evil.test/VBCABLE_Driver_Pack45.zip">driver</a>')
    with pytest.raises(ValueError):
        installer.discover_package('No driver')


@pytest.mark.parametrize('path', ['../pwn.exe', '/absolute', 'C:/bad', 'folder/../../bad'])
def test_installer_rejects_zip_traversal(tmp_path, path):
    with pytest.raises(ValueError):
        installer.extract_package(zipped({path: b'bad'}), tmp_path)


def test_installer_requires_expected_windows_exe(tmp_path):
    with pytest.raises(ValueError):
        installer.extract_package(zipped({'VBCABLE_Setup_x64.exe': b'not PE'}), tmp_path)
    with pytest.raises(ValueError):
        installer.extract_package(zipped({'unknown.exe': b'MZ'}), tmp_path)


def test_https_hosts_and_credentials():
    for url in ['http://github.com/a', 'https://evil.test/a', 'https://user:password@github.com/a']:
        with pytest.raises(ValueError):
            validate_url(url, {'github.com'})


def test_settings_roundtrip_and_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'data_dir', lambda: tmp_path)
    original = settings.Settings(port=12345, theme='dark', gain=1.5, auto_start=True)
    original.save()
    assert settings.Settings.load() == original
    (tmp_path / 'settings.json').write_text('{invalid')
    assert settings.Settings.load() == settings.Settings()
    (tmp_path / 'settings.json').write_text(json.dumps({'port': -1}))
    assert settings.Settings.load().port == 8765


def test_release_selection_requires_assets_and_new_version(monkeypatch):
    release = {'tag_name': 'v1.0.1', 'assets': [
        {'name': name, 'browser_download_url': f'https://github.com/mycodehive/airear/releases/download/v1.0.1/{name}'}
        for name in ['AirEar.exe', 'SHA256SUMS.txt']]}
    monkeypatch.setattr(updater, 'fetch', lambda *a: json.dumps(release).encode())
    assert updater.latest_release()['tag'] == 'v1.0.1'
    release['prerelease'] = True
    assert updater.latest_release() is None
    release.pop('prerelease')
    release['assets'][0]['browser_download_url'] = 'https://evil.test/app.exe'
    with pytest.raises(ValueError):
        updater.latest_release()


def test_update_rejects_checksum_mismatch_and_removes_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(updater, 'fetch', lambda *a: b'0' * 64 + b'  AirEar.exe\n')
    monkeypatch.setattr(updater, 'download', lambda url, path, *args: path.write_bytes(b'MZdummy'))
    with pytest.raises(ValueError, match='무결성'):
        updater.stage_update({'assets': {'SHA256SUMS.txt': 'https://github.com/checks', 'AirEar.exe': 'https://github.com/app'}})
    assert not list(tmp_path.rglob('*.exe'))


def test_installer_refusal_never_downloads(tmp_path, monkeypatch):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: 0)
    monkeypatch.setattr(QMessageBox, 'clickedButton', lambda self: None)
    monkeypatch.setattr(installer, 'prepare_installer', lambda: pytest.fail('Download before consent'))
    installer.install_vbcable()
    assert app
