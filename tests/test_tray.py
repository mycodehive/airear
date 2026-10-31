"""Qt tray event behavior with platform tray availability simulated."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon
from airear.tray import install_tray


def test_minimize_hides_and_tray_restores(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: True)
    window = QMainWindow()
    window.closing = False
    install_tray(window)
    window.show()
    window.showMinimized()
    app.processEvents()
    assert not window.isVisible()
    window.tray_controller.restore()
    app.processEvents()
    assert window.isVisible() and not window.isMinimized()
    window.tray_controller.icon.hide()
    window.close()


def test_without_system_tray_minimize_keeps_window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QSystemTrayIcon, 'isSystemTrayAvailable', lambda: False)
    window = QMainWindow()
    window.closing = False
    install_tray(window)
    window.show()
    window.showMinimized()
    app.processEvents()
    assert window.isVisible()
    window.close()
