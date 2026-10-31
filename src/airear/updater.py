"""GitHub release discovery and consent-based verified in-place frozen EXE updates."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

from . import __version__
from .downloads import download, fetch
from .paths import data_dir

API = "https://api.github.com/repos/mycodehive/airear/releases/latest"
HOSTS = {"api.github.com", "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


def version_tuple(tag):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if not match:
        raise ValueError("정식 버전 번호를 확인하지 못했습니다.")
    return tuple(map(int, match.groups()))


def latest_release():
    release = json.loads(fetch(API, HOSTS))
    if release.get("draft") or release.get("prerelease"):
        return None
    if version_tuple(release["tag_name"]) <= version_tuple(__version__):
        return None
    assets = {a["name"]: a["browser_download_url"] for a in release["assets"]}
    if not {"WindowsAudio_iPhone.exe", "SHA256SUMS.txt"} <= assets.keys():
        raise ValueError("릴리스에 EXE 또는 검증 파일이 없습니다.")
    # Assets must belong to this exact repository; redirected CDN permitted by downloader.
    prefix = "https://github.com/mycodehive/airear/releases/download/" + release["tag_name"] + "/"
    for name in ("WindowsAudio_iPhone.exe", "SHA256SUMS.txt"):
        if not assets[name].startswith(prefix):
            raise ValueError("릴리스 파일 주소가 일치하지 않습니다.")
    return {"tag": release["tag_name"], "assets": assets}


def stage_update(release):
    import tempfile
    directory = Path(tempfile.mkdtemp(prefix="update-", dir=data_dir()))
    exe = directory / "WindowsAudio_iPhone.exe"
    checksums = fetch(release["assets"]["SHA256SUMS.txt"], HOSTS, 8192).decode("utf-8")
    match = re.search(r"^([a-fA-F0-9]{64})\s+\*?WindowsAudio_iPhone\.exe\s*$", checksums, re.M)
    if not match:
        raise ValueError("체크섬 파일 형식이 올바르지 않습니다.")
    download(release["assets"]["WindowsAudio_iPhone.exe"], exe, HOSTS, 600_000_000)
    with exe.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        stream.seek(0)
        magic = stream.read(2)
    if digest.lower() != match[1].lower() or magic != b"MZ":
        exe.unlink(missing_ok=True)
        raise ValueError("업데이트 무결성 검사 실패")
    return exe


def launch_replacement(staged: Path):
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        raise RuntimeError("자동 교체는 Windows 배포 EXE에서만 사용할 수 있습니다.")
    target = Path(sys.executable).resolve()
    script = staged.parent / "apply.ps1"
    def literal(path):
        return "'" + str(path).replace("'", "''") + "'"
    # User-level helper; never uses elevation. Backup and rollback on failed copy.
    from .i18n import tr
    update_failed = tr("업데이트 실패. 기존 EXE를 다시 실행하세요.").replace("'", "''")
    script.write_text(
        "$ErrorActionPreference='Stop'\n"
        f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue\n"
        f"$target={literal(target)}\n$source={literal(staged)}\n$backup=$target+'.previous'\n"
        "try {\n Copy-Item -LiteralPath $target -Destination $backup -Force\n"
        " Copy-Item -LiteralPath $source -Destination $target -Force\n"
        " Start-Process -FilePath $target\n} catch {\n"
        " if (Test-Path -LiteralPath $backup) { Copy-Item -LiteralPath $backup -Destination $target -Force }\n"
        " Add-Type -AssemblyName PresentationFramework\n"
        f" [System.Windows.MessageBox]::Show('{update_failed}')\n}}\n",
        encoding="utf-8-sig")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                     creationflags=0x08000000, close_fds=True)


def check_for_update(parent=None, silent=False):
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QMessageBox
    if getattr(parent, "_update_busy", False):
        return
    if parent is not None:
        parent._update_busy = True
    class Result(QObject):
        discovered = Signal(object)
        staged = Signal(str)
        failed = Signal(str)
    result = Result(parent)
    def finish():
        if parent is not None:
            parent._update_busy = False
        result.deleteLater()
    def failed(message):
        if not silent:
            QMessageBox.warning(parent, "업데이트", message)
        finish()
    def discovered(release):
        if release is None:
            if not silent:
                QMessageBox.information(parent, "업데이트", "현재 최신 정식 버전입니다.")
            finish()
            return
        answer = QMessageBox.question(parent, "업데이트", f"{release['tag']} 버전이 있습니다.\n"
                                      "EXE를 다운로드하고 SHA256을 확인한 뒤 프로그램을 종료하여 교체할까요?\n"
                                      "서명되지 않은 배포 파일은 SmartScreen 경고가 나타날 수 있습니다.")
        if answer != QMessageBox.StandardButton.Yes:
            finish()
            return
        def stage():
            try:
                result.staged.emit(str(stage_update(release)))
            except Exception as error:
                result.failed.emit(str(error))
        threading.Thread(target=stage, daemon=True, name="release-download").start()
    def staged(path):
        try:
            if getattr(sys, "frozen", False) and sys.platform == "win32":
                launch_replacement(Path(path))
                # closeEvent shuts down server/capture and persists settings.
                if parent is not None:
                    parent.close()
            else:
                QMessageBox.information(parent, "업데이트", "다운로드 및 검증 완료:\n" + path + "\nWindows에서 실행하세요.")
            finish()
        except Exception as error:
            failed(str(error))
    result.discovered.connect(discovered)
    result.staged.connect(staged)
    result.failed.connect(failed)
    def work():
        try:
            result.discovered.emit(latest_release())
        except Exception as error:
            result.failed.emit(str(error))
    threading.Thread(target=work, daemon=True, name="release-check").start()
