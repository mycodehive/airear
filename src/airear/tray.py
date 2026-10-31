"""Keep streaming while minimized; explicit tray exit performs normal shutdown."""
from PySide6.QtCore import QObject, QEvent, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from importlib.resources import files

from .i18n import get_localizer, tr


class TrayController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.icon = QSystemTrayIcon(QIcon(str(files('airear').joinpath('assets/airear.ico'))), window)
        menu = QMenu(window)
        self.restore_action = QAction(menu)
        self.exit_action = QAction(menu)
        self.restore_action.triggered.connect(self.restore)
        self.exit_action.triggered.connect(self.exit)
        menu.addAction(self.restore_action)
        menu.addSeparator()
        menu.addAction(self.exit_action)
        self.icon.setContextMenu(menu)
        self.icon.activated.connect(self.activated)
        get_localizer().changed.connect(self.translate)
        self.translate()
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        if self.available:
            self.icon.show()
        window.installEventFilter(self)
        QApplication.instance().aboutToQuit.connect(self.icon.hide)

    def translate(self):
        self.restore_action.setText(tr('AirEar 열기'))
        self.exit_action.setText(tr('종료'))
        self.icon.setToolTip(tr('AirEar · 휴대폰으로 PC 소리 듣기'))

    def eventFilter(self, watched, event):
        if watched is getattr(self, 'window', None) and event.type() == QEvent.Type.WindowStateChange:
            if self.available and self.window.isMinimized():
                QTimer.singleShot(0, self.hide_minimized)
        return False

    def hide_minimized(self):
        if self.window.isMinimized() and not self.window.closing:
            self.window.hide()

    def restore(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore()

    def exit(self):
        self.restore()
        self.window.close()


def install_tray(window):
    window.tray_controller = TrayController(window)
