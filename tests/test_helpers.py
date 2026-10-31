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
    release = {'tag_name': 'v1.0.4', 'assets': [
        {'name': name, 'browser_download_url': f'https://github.com/mycodehive/airear/releases/download/v1.0.4/{name}'}
        for name in ['AirEar.exe', 'SHA256SUMS.txt']]}
    monkeypatch.setattr(updater, 'fetch', lambda *a: json.dumps(release).encode())
    assert updater.latest_release()['tag'] == 'v1.0.4'
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


def test_failed_installer_offers_manual_path(monkeypatch):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(installer.sys, 'platform', 'win32')
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: 0)
    monkeypatch.setattr(QMessageBox, 'clickedButton', lambda self: next(b for b in self.buttons() if b.text() == '설치하기'))
    def fail():
        raise ValueError('Signature unavailable')
    monkeypatch.setattr(installer, 'prepare_installer', fail)
    monkeypatch.setattr(installer.threading, 'Thread', lambda target, **kwargs: SimpleNamespace(start=target))
    calls = []
    monkeypatch.setattr(installer, 'manual_install_vbcable', lambda parent, reason='': calls.append(reason))
    installer.install_vbcable()
    assert calls == ['Signature unavailable']
    assert app


def test_manual_instructions_open_official_site_and_copy(monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton
    app = QApplication.instance() or QApplication([])
    opened = []
    monkeypatch.setattr(QDesktopServices, 'openUrl', lambda url: opened.append(url.toString()) or True)
    def inspect(dialog):
        buttons = {b.text(): b for b in dialog.findChildren(QPushButton)}
        buttons['공식 다운로드 페이지 열기'].click()
        buttons['설치 안내 복사'].click()
        return 0
    monkeypatch.setattr(QDialog, 'exec', inspect)
    monkeypatch.setattr(installer, 'prepare_installer', lambda: pytest.fail('Manual help must not download or execute'))
    installer.manual_install_vbcable(reason='Signature unavailable')
    assert opened == [installer.OFFICIAL_PAGE]
    assert installer.OFFICIAL_PAGE in app.clipboard().text()
    assert 'VBCABLE_Setup_x64.exe' in app.clipboard().text()


def test_download_reports_bytes_and_rejects_truncation(tmp_path, monkeypatch):
    from airear import downloads
    from types import SimpleNamespace
    import io
    def response(data, size):
        stream = io.BytesIO(data)
        stream.headers = {'Content-Length': str(size)}
        return stream
    current = [response(b'abc', 3)]
    monkeypatch.setattr(downloads, 'build_opener', lambda *a: SimpleNamespace(open=lambda *a, **k: current[0]))
    updates = []
    target = tmp_path / 'app.exe'
    downloads.download('https://github.com/app', target, {'github.com'}, 100, lambda n, total: updates.append((n, total)))
    assert updates == [(0, 3), (3, 3)]
    assert target.read_bytes() == b'abc'
    current[0] = response(b'ab', 3)
    with pytest.raises(ValueError):
        downloads.download('https://github.com/app', target, {'github.com'}, 100)
    assert not target.exists()


def test_update_button_shows_download_progress_and_recovers(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.update_button = QPushButton('업데이트 확인', parent)
    monkeypatch.setattr(updater, 'latest_release', lambda: {'tag': 'v9.0.0'})
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: None)
    monkeypatch.setattr(updater.sys, 'frozen', False, raising=False)
    monkeypatch.setattr(updater.threading, 'Thread', lambda target, **k: SimpleNamespace(start=target))
    seen = []
    def staged(release, progress):
        assert not parent.update_button.isEnabled()
        progress('download', 25)
        seen.append(parent.update_button.text())
        progress('download', 75)
        seen.append(parent.update_button.text())
        progress('verify', 100)
        seen.append(parent.update_button.text())
        return tmp_path / 'AirEar.exe'
    monkeypatch.setattr(updater, 'stage_update', staged)
    updater.check_for_update(parent)
    assert '25%' in seen[0] and '75%' in seen[1] and '100%' in seen[2]
    assert parent.update_button.isEnabled() and not parent._update_busy
    parent.close()
    assert app
