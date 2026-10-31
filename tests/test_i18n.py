"""Runtime pack edits and language switching must preserve source text and user data."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QWidget
from airear import i18n


def test_live_pack_switch_and_override(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, 'data_dir', lambda: tmp_path)
    app = QApplication.instance() or QApplication([])
    manager = i18n.Localizer()
    manager.timer.stop()
    host = QWidget()
    label = QLabel('서버 관리', host)
    error = QLabel('오디오 캡처 재시도 중: Device unavailable', host)
    entry = QLineEdit('서버 관리', host)
    clients = QListWidget(host)
    clients.addItem('192.168.1.3 · 연결됨')
    host.show()
    manager.set_language('en')
    assert label.text() == 'Server'
    assert error.text() == 'Retrying audio capture: Device unavailable'
    assert clients.item(0).text() == '192.168.1.3 · Connected'
    assert entry.text() == '서버 관리'
    manager.set_language('ko')
    assert label.text() == '서버 관리'
    assert error.text() == '오디오 캡처 재시도 중: Device unavailable'
    assert clients.item(0).text() == '192.168.1.3 · 연결됨'
    folder = tmp_path / 'languages'
    folder.mkdir(exist_ok=True)
    path = folder / 'en.json'
    path.write_text(json.dumps({'name':'English', 'strings':{'서버 관리':'Server controls'}}))
    manager.set_language('en')
    assert label.text() == 'Server controls'
    path.write_text(json.dumps({'name':'English', 'strings':{'서버 관리':'Updated controls'}}))
    manager.reload()
    assert label.text() == 'Updated controls'
    path.write_text('{broken')
    manager.reload()
    assert label.text() == 'Server'
    host.close()
    assert app


def test_default_language_files_are_editable_and_not_overwritten(tmp_path, monkeypatch):
    from airear import i18n
    import json
    monkeypatch.setattr(i18n, 'data_dir', lambda: tmp_path)
    folder = i18n.ensure_language_files()
    assert (folder / 'ko.json').is_file() and (folder / 'en.json').is_file()
    pack = json.loads((folder / 'en.json').read_text(encoding='utf-8'))
    pack['strings']['설정'] = 'My settings'
    (folder / 'en.json').write_text(json.dumps(pack), encoding='utf-8')
    i18n.ensure_language_files()
    assert i18n.load_language('en')['strings']['설정'] == 'My settings'
