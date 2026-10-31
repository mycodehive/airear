"""Consent-first official VB-CABLE installation helper, never bundled driver."""
import ctypes
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import threading
from urllib.parse import urljoin
import zipfile

from .downloads import download, fetch, validate_url
from .paths import data_dir

OFFICIAL_PAGE = "https://vb-audio.com/Cable/"
HOSTS = {"vb-audio.com", "download.vb-audio.com", "www.vb-audio.com"}


def discover_package(page: str) -> str:
    # Resolve the current link from the publisher page, not a guessed download URL.
    for href in re.findall(r'''href\s*=\s*["']([^"']+)["']''', page, re.I):
        if re.search(r"/VBCABLE_Driver_Pack\d+\.zip$", href, re.I):
            return validate_url(urljoin(OFFICIAL_PAGE, href), HOSTS)
    raise ValueError("공식 드라이버 링크를 찾지 못했습니다. 공식 사이트에서 설치하세요.")


def extract_package(data: bytes, target: Path) -> Path:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.infolist()) > 256 or sum(i.file_size for i in archive.infolist()) > 80_000_000:
            raise ValueError("예상하지 못한 드라이버 압축 구조입니다.")
        for info in archive.infolist():
            path = PurePosixPath(info.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in info.filename or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("안전하지 않은 압축 경로입니다.")
        archive.extractall(target)
    candidates = list(target.rglob("VBCABLE_Setup_x64.exe"))
    if len(candidates) != 1:
        raise ValueError("x64 공식 설치 파일을 확인하지 못했습니다. 공식 사이트에서 수동 설치하세요.")
    exe = candidates[0]
    if exe.read_bytes()[:2] != b"MZ":
        raise ValueError("Windows 설치 파일 형식이 아닙니다.")
    return exe


def verify_publisher(exe: Path):
    escaped = str(exe).replace("'", "''")
    script = (f"$s=Get-AuthenticodeSignature -LiteralPath '{escaped}'; "
              "@{Status=$s.Status.ToString(); Subject=$s.SignerCertificate.Subject} | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, timeout=30, creationflags=0x08000000)
    info = json.loads(result.stdout)
    if info.get("Status") != "Valid" or not re.search(r"VB[ -]?Audio|Vincent\s+Burel", info.get("Subject", ""), re.I):
        raise ValueError("VB-Audio 설치 프로그램의 유효한 서명을 확인하지 못했습니다. 자동 실행을 중단합니다.")


def prepare_installer() -> Path:
    page = fetch(OFFICIAL_PAGE, HOSTS).decode("utf-8", errors="replace")
    package = discover_package(page)
    import tempfile
    folder = Path(tempfile.mkdtemp(prefix="vbcable-", dir=data_dir()))
    archive = folder / "driver.zip"
    download(package, archive, HOSTS, 20_000_000)
    exe = extract_package(archive.read_bytes(), folder / "driver")
    verify_publisher(exe)
    return exe



MANUAL_STEPS = (
    "1. ‘공식 다운로드 페이지 열기’를 눌러 Windows용 VB-CABLE ZIP을 다운로드하세요.\n"
    "2. ZIP을 모두 압축 해제한 뒤 VBCABLE_Setup_x64.exe를 마우스 오른쪽 버튼으로 클릭하고 ‘관리자 권한으로 실행’을 선택하세요.\n"
    "3. 공식 설치 화면에서 Install Driver를 누르고, 설치가 끝나면 안내에 따라 PC를 재부팅하세요.\n"
    "4. AirEar를 다시 열어 오디오 장치 ‘새로고침’을 누르고 CABLE Input 장치를 선택하세요.\n"
    "5. PC 스피커를 무음으로 쓰려면 Windows 소리 설정의 출력도 CABLE Input으로 바꾸세요."
)


def manual_install_vbcable(parent=None, reason=""):
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout, QMessageBox
    dialog = QDialog(parent)
    dialog.setWindowTitle("VB-CABLE 수동 설치")
    dialog.setMinimumWidth(480)
    layout = QVBoxLayout(dialog)
    if reason:
        summary = QLabel("자동 설치를 완료하지 못했습니다. 공식 사이트에서 직접 설치할 수 있습니다.")
        summary.setWordWrap(True)
        layout.addWidget(summary)
        details = QLabel(reason)
        details.setWordWrap(True)
        details.setTextFormat(Qt.TextFormat.PlainText)
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(details)
    steps = QLabel(MANUAL_STEPS)
    steps.setWordWrap(True)
    steps.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(steps)
    address = QLabel(OFFICIAL_PAGE)
    address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(address)
    official = QPushButton("공식 다운로드 페이지 열기")
    def open_official():
        if not QDesktopServices.openUrl(QUrl(OFFICIAL_PAGE)):
            QMessageBox.information(dialog, "VB-CABLE", "브라우저를 열지 못했습니다. ‘설치 안내 복사’를 누른 뒤 주소를 브라우저에 붙여 넣으세요.")
    official.clicked.connect(open_official)
    layout.addWidget(official)
    copy = QPushButton("설치 안내 복사")
    def copy_steps():
        from .i18n import tr
        QApplication.clipboard().setText(OFFICIAL_PAGE + "\n\n" + tr(MANUAL_STEPS))
    copy.clicked.connect(copy_steps)
    layout.addWidget(copy)
    sound = QPushButton("Windows 소리 설정 열기")
    def open_sound():
        if sys.platform == "win32":
            QDesktopServices.openUrl(QUrl("ms-settings:sound"))
        else:
            QMessageBox.information(dialog, "VB-CABLE", "드라이버 설치는 Windows에서 지원합니다.")
    sound.clicked.connect(open_sound)
    layout.addWidget(sound)
    close = QPushButton("닫기")
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    dialog.exec()


def install_vbcable(parent=None):
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QMessageBox
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("VB-CABLE 설치 안내")
    dialog.setText("PC 스피커에서 소리를 출력하지 않고 휴대폰으로만 전송하려면 VB-CABLE 가상 오디오 드라이버가 필요합니다.\n\n"
                   "VB-CABLE은 외부 개발사인 VB-Audio에서 제공하는 가상 오디오 장치입니다.\n"
                   "설치 시 관리자 권한이 필요할 수 있으며, 설치 후 재부팅해야 할 수 있습니다.\n\n지금 설치하시겠습니까?")
    install = dialog.addButton("설치하기", QMessageBox.ButtonRole.AcceptRole)
    manual = dialog.addButton("수동 설치 안내", QMessageBox.ButtonRole.ActionRole)
    dialog.addButton("나중에 설치", QMessageBox.ButtonRole.RejectRole)
    dialog.addButton("취소", QMessageBox.ButtonRole.RejectRole)
    dialog.exec()
    if dialog.clickedButton() is manual:
        manual_install_vbcable(parent)
        return
    if dialog.clickedButton() is not install:
        return
    if sys.platform != "win32":
        QMessageBox.information(parent, "VB-CABLE", "드라이버 설치는 Windows에서 지원합니다.")
        return
    class Result(QObject):
        ready = Signal(str)
        failed = Signal(str)
    result = Result(parent)
    # Parent retains QObject until worker has delivered its queued result.
    def ready(path):
        # ShellExecute shows official interactive installer and UAC only at installation.
        value = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, None, str(Path(path).parent), 1)
        if value <= 32:
            manual_install_vbcable(parent, "설치 실행이 취소되었거나 실패했습니다. 일반 장치로 시험할 수 있습니다.")
        else:
            QMessageBox.information(parent, "VB-CABLE", "공식 설치 화면에서 Install Driver를 진행하세요.\n"
                                    "설치 화면을 열었다는 사실만 확인했으며 설치 성공은 아직 확인되지 않았습니다.\n"
                                    "완료 후 필요하면 재부팅하고 ‘장치 새로고침’을 누르세요.")
        result.deleteLater()
    def failed(message):
        manual_install_vbcable(parent, message)
        result.deleteLater()
    result.ready.connect(ready)
    result.failed.connect(failed)
    def work():
        try:
            result.ready.emit(str(prepare_installer()))
        except Exception as error:
            result.failed.emit(str(error))
    threading.Thread(target=work, daemon=True, name="vbcable-download").start()
