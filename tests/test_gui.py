"""Real Qt layout smoke checks; desktop/audio/network hardware is deliberately stubbed."""
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize('scale', ['1', '1.25', '1.5', '2'])
def test_qt_layout_at_dpi(scale, tmp_path):
    pytest.importorskip('PySide6')
    source = r'''
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, QRect
from airear.gui import Window
from airear.settings import Settings
class Audio:
    gain=1.0
    muted=False
    error=''
    level=0.3
    def select(self, value): pass
class Server:
    pin='12345678'
    running=True
    def snapshot(self):
        return {'running':self.running,'error':'','clients':[],'port':8765}
    def stop(self): self.running=False
Window.refresh_devices=lambda self: None
app=QApplication([])
for theme in ('light','dark'):
    window=Window(Settings(check_updates=False, theme=theme, advertised_host='192.168.1.2'), Audio(), Server())
    window.resize(480,420)
    window.show()
    app.processEvents()
    window.update_url()
    app.processEvents()
    center=window.qr.mapTo(window.scroll.widget(),window.qr.rect().center())
    window.scroll.ensureVisible(center.x(),center.y(),136,136)
    app.processEvents()
    assert window.qr.width() == 256 and window.qr.height() == 256
    assert window.qr.pixmap() is not None and not window.qr.pixmap().isNull()
    viewport=window.scroll.viewport()
    position=window.qr.mapTo(viewport,QPoint(0,0))
    assert viewport.rect().contains(QRect(position, window.qr.size())), (position,viewport.size())
    assert window.scroll.verticalScrollBar().maximum()>0
    assert not window.sidebar.isVisible()
    assert ('#11151d' if theme == 'dark' else '#f3f6fb') in window.styleSheet()
    assert window.update_timer.interval()==4*60*60*1000
    window.settings.language='en'
    assert window.text('서버 관리')=='Server'
    assert window.text('번역 추가 예정')=='번역 추가 예정'
    window.timer.stop()
    window.update_timer.stop()
    window.closing=True
    window.close()
    window.executor.shutdown(wait=True)
'''
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=scale,
                       LOCALAPPDATA=str(tmp_path))
    result = subprocess.run([sys.executable, '-c', source], env=environment,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
