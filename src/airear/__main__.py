import logging
from logging.handlers import RotatingFileHandler
import sys

from .paths import data_dir, log_path


def main():
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication(sys.argv)
    from .i18n import get_localizer
    from .settings import Settings
    get_localizer().set_language(Settings.load().language)
    app.setApplicationName("AirEar")
    app.setOrganizationName("mycodehive")
    from PySide6.QtGui import QIcon
    from importlib.resources import files
    app.setWindowIcon(QIcon(str(files("airear").joinpath("assets/airear.ico"))))
    handler = RotatingFileHandler(log_path(), maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    # Never enable aiohttp access logs (query/auth material must not be logged).
    logging.getLogger("aiohttp.access").disabled = True
    lock = QLockFile(str(data_dir() / "instance.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "AirEar", "이미 실행 중입니다.")
        return 0
    def exception_hook(kind, value, tb):
        logging.error("Unhandled application error", exc_info=(kind, value, tb))
        QMessageBox.critical(None, "AirEar", "오류가 발생했습니다. 진단 로그를 확인하세요.")
    sys.excepthook = exception_hook
    if "--smoke-test" in sys.argv:
        # Frozen executable import/assets/Qt smoke check; no driver or network access.
        from .audio import AudioEngine
        from .server import Runtime
        from .gui import Window
        from importlib.resources import files
        assert files("airear").joinpath("web/index.html").is_file()
        assert AudioEngine and Runtime and Window
        QTimer.singleShot(0, app.quit)
        return app.exec()
    try:
        from .gui import Window
        window = Window()
        window.show()
        return app.exec()
    except Exception:
        logging.exception("Startup failed")
        QMessageBox.critical(None, "AirEar", "시작하지 못했습니다. 로그 파일을 확인하세요.")
        return 1
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
