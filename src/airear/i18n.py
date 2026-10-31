"""JSON language packs shared by desktop controls and the browser receiver."""
from __future__ import annotations
import json
import logging
import re
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QListWidget, QWidget
from PySide6.QtGui import QAction

from .paths import data_dir

BUILTIN = Path(__file__).parent / 'languages'
LOG = logging.getLogger(__name__)


def load_language(code: str) -> dict:
    if not code or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in code):
        code = 'en'
    result = {'name': code, 'strings': {}, 'web': {}}
    for folder in (BUILTIN, data_dir() / 'languages'):
        try:
            raw = json.loads((folder / f'{code}.json').read_text(encoding='utf-8'))
            if not isinstance(raw, dict):
                continue
            if isinstance(raw.get('name'), str):
                result['name'] = raw['name']
            for key in ('strings', 'web'):
                result[key].update({k: v for k, v in raw.get(key, {}).items() if isinstance(k, str) and isinstance(v, str)})
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, AttributeError, OSError):
            LOG.warning('Invalid language pack: %s', code)
    return result


def available_languages() -> list[dict]:
    codes = {'ko', 'en'}
    for folder in (BUILTIN, data_dir() / 'languages'):
        if folder.exists():
            codes.update(p.stem for p in folder.glob('*.json'))
    return [{'code': code, 'name': load_language(code)['name']} for code in sorted(codes)]


class Localizer(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.language = 'ko'
        self.pack = load_language('ko')
        self._signature = ''
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.reload)
        self.timer.start(250)

    def set_language(self, code):
        self.language = code
        self.reload(force=True)

    def t(self, source: str, **values) -> str:
        strings = self.pack.get('strings', {})
        if source in strings:
            result = strings[source]
        else:
            result = source
            # Dynamic labels are assembled from source fragments. Longest first
            # preserves exact paragraph translations and their interpolation values.
            for key in sorted(strings, key=len, reverse=True):
                if len(key) > 1 and re.search("[가-힣]", key) and key in result:
                    result = result.replace(key, strings[key])
        if values:
            try:
                return result.format(**values)
            except (ValueError, KeyError):
                return source.format(**values)
        return result

    def _property(self, obj, getter, setter):
        if not hasattr(obj, getter) or not hasattr(obj, setter):
            return
        current = getattr(obj, getter)()
        if not isinstance(current, str) or not current:
            return
        key = '_language_' + getter
        old = obj.property(key)
        source = old[0] if isinstance(old, list) and len(old) == 2 and current == old[1] else current
        rendered = self.t(source)
        obj.setProperty(key, [source, rendered])
        if current != rendered:
            getattr(obj, setter)(rendered)

    def apply(self):
        app = QApplication.instance()
        if app is None:
            return
        for top in app.topLevelWidgets():
            widgets = [top] + top.findChildren(QWidget) + top.findChildren(QAction)
            for obj in widgets:
                for getter, setter in [('text','setText'), ('windowTitle','setWindowTitle'),
                                       ('toolTip','setToolTip'), ('placeholderText','setPlaceholderText'),
                                       ('accessibleName','setAccessibleName'),
                                       ('informativeText','setInformativeText'), ('detailedText','setDetailedText')]:
                    # Never rewrite editable content entered by the user.
                    if getter == 'text' and isinstance(obj, QLineEdit):
                        continue
                    self._property(obj, getter, setter)
                if isinstance(obj, QListWidget):
                    role = Qt.ItemDataRole.UserRole + 30
                    for index in range(obj.count()):
                        item = obj.item(index)
                        current = item.text()
                        old = item.data(role)
                        source = old[0] if isinstance(old, list) and len(old) == 2 and current == old[1] else current
                        rendered = self.t(source)
                        item.setData(role, [source, rendered])
                        if current != rendered:
                            item.setText(rendered)
                if isinstance(obj, QComboBox):
                    for index in range(obj.count()):
                        current = obj.itemText(index)
                        key = '_language_item_' + str(index)
                        old = obj.property(key)
                        source = old[0] if isinstance(old, list) and len(old) == 2 and current == old[1] else current
                        rendered = self.t(source)
                        obj.setProperty(key, [source, rendered])
                        if current != rendered:
                            blocked = obj.blockSignals(True)
                            obj.setItemText(index, rendered)
                            obj.blockSignals(blocked)

    def reload(self, force=False):
        pack = load_language(self.language)
        signature = json.dumps(pack, sort_keys=True, ensure_ascii=False)
        if force or signature != self._signature:
            self.pack = pack
            self._signature = signature
            self.changed.emit()
        self.apply()


_manager = None


def get_localizer() -> Localizer:
    global _manager
    if _manager is None:
        _manager = Localizer()
    return _manager


def tr(source: str, **values) -> str:
    return get_localizer().t(source, **values)
