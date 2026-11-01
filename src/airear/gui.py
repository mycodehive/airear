"""Moaham-inspired desktop control surface; all blocking operations run off Qt's thread."""
from __future__ import annotations

import ipaddress
import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import qrcode
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSlider, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from .audio import AudioEngine
from .paths import log_path
from .server import Runtime
from .settings import Settings
from .i18n import available_languages, get_localizer, tr

LOG = logging.getLogger(__name__)



class _Bridge(QObject):
    done = Signal(object, object, object)


def lan_addresses() -> list[str]:
    """Return private IPv4 addresses assigned to active local interfaces."""
    addresses: set[str] = set()
    try:
        from PySide6.QtNetwork import QNetworkInterface

        for interface in QNetworkInterface.allInterfaces():
            flags = interface.flags()
            required = QNetworkInterface.InterfaceFlag.IsUp | QNetworkInterface.InterfaceFlag.IsRunning
            if flags & required != required:
                continue
            for entry in interface.addressEntries():
                text = entry.ip().toString()
                if _is_private_lan_ipv4(text):
                    addresses.add(text)
    except Exception:
        LOG.debug('Qt network interface discovery failed; using hostname fallback', exc_info=True)

    # Hostname lookup is a fallback only. Filter it the same way as interface
    # enumeration so a public/VPN address can never become the QR default.
    if not addresses:
        try:
            for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                text = item[4][0]
                if _is_private_lan_ipv4(text):
                    addresses.add(text)
        except OSError:
            LOG.debug('Hostname address lookup failed', exc_info=True)

    def priority(text: str) -> tuple[int, int]:
        address = ipaddress.IPv4Address(text)
        # Prefer the common home/office Wi-Fi range, then other RFC1918 LANs.
        network_priority = 0 if address in ipaddress.IPv4Network('192.168.0.0/16') else 1
        return network_priority, int(address)

    return sorted(addresses, key=priority)


def _is_private_lan_ipv4(value: str) -> bool:
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return False
    return any(address in network for network in (
        ipaddress.IPv4Network('10.0.0.0/8'),
        ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'),
    ))


class Window(QMainWindow):
    def __init__(self, settings=None, engine=None, runtime=None):
        super().__init__()
        self.settings = settings or Settings.load()
        self.localizer = get_localizer()
        self.localizer.set_language(self.settings.language)
        self.engine = engine or AudioEngine()
        self.runtime = runtime or Runtime(self.engine)
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='airear-ui')
        self.bridge = _Bridge(self)
        self.bridge.done.connect(self._finished)
        self.busy = False
        self.closing = False
        self.first_scan = True
        self.cached_clients = []
        self._url = ''
        self._active_protocol = 'http'
        self._active_port = self.settings.port
        self.setWindowTitle('AirEar · Windows Audio → Phone 1.0.4')
        self.resize(840, 720)
        self.setMinimumSize(400, 350)
        self.engine.gain = self.settings.gain
        self.engine.select(self.settings.device_id)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setFixedWidth(190)
        nav = QVBoxLayout(self.sidebar)
        nav.setContentsMargins(18, 25, 18, 22)
        brand = QLabel('◉  AirEar')
        brand.setObjectName('brand')
        nav.addWidget(brand)
        subtitle = QLabel('WINDOWS AUDIO → PHONE')
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet('font-size: 10px; color: #8295b0;')
        nav.addWidget(subtitle)
        nav.addSpacing(30)
        for title, section in [('서버 관리', 'server'), ('오디오 설정', 'audio'), ('휴대폰 연결', 'phone'), ('로그 및 진단', 'logs')]:
            button = QPushButton(title)
            button.clicked.connect(lambda _=False, name=section: self.scroll.ensureWidgetVisible(self.sections[name]))
            nav.addWidget(button)
        nav.addStretch()
        nav.addWidget(QLabel('개인 LAN 전용\nv1.0.4'))
        outer.addWidget(self.sidebar)
        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(22, 16, 22, 16)
        header = QHBoxLayout()
        title = QLabel('Windows Audio → Phone')
        title.setObjectName('heading')
        title.setWordWrap(True)
        header.addWidget(title)
        header.addStretch()
        self.state = QLabel('● 중지됨 · 수신기 0대')
        header.addWidget(self.state)
        self._button(header, '설정', self.edit_settings)
        column.addLayout(header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.cards = QVBoxLayout(content)
        self.cards.setSpacing(16)
        self.cards.setContentsMargins(0, 12, 4, 12)
        self.sections = {}
        self._build_server()
        self._build_audio()
        self._build_phone()
        self._build_logs()
        self.cards.addStretch()
        self.scroll.setWidget(content)
        column.addWidget(self.scroll)
        outer.addWidget(right, 1)
        self.apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(lambda *_: self.apply_theme())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(500)
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(4 * 60 * 60 * 1000)
        self.update_timer.timeout.connect(self.automatic_update)
        self.update_timer.start()
        self.localizer.changed.connect(self.retranslate)
        self.localizer.apply()
        from .tray import install_tray
        install_tray(self)
        self.refresh_devices()
        if self.settings.auto_start:
            QTimer.singleShot(300, self.start_server)
        if self.settings.check_updates:
            QTimer.singleShot(3500, self.automatic_update)

    def text(self, source):
        if self.localizer.language != self.settings.language:
            self.localizer.set_language(self.settings.language)
        return tr(source)

    def retranslate(self):
        if hasattr(self, "qr"):
            self._url = ""
            self.update_url()
            self.refresh_status()
            self.pin_label.setText(f'접속 PIN  {self.runtime.pin}')

    def change_language(self, code):
        self.settings.language = code
        self.settings.save()
        self.localizer.set_language(code)

    def _card(self, name, title, subtitle):
        frame = QFrame()
        frame.setObjectName('card')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        heading = QLabel(title)
        heading.setObjectName('cardTitle')
        layout.addWidget(heading)
        caption = QLabel(subtitle)
        caption.setWordWrap(True)
        caption.setObjectName('muted')
        layout.addWidget(caption)
        self.cards.addWidget(frame)
        self.sections[name] = frame
        return layout

    def _button(self, layout, title, slot):
        button = QPushButton(title)
        button.clicked.connect(slot)
        layout.addWidget(button)
        return button

    def _build_server(self):
        card = self._card('server', '01  서버 관리', 'Windows의 소리를 같은 Wi-Fi에 연결된 휴대폰으로 전달합니다.')
        row = QHBoxLayout()
        self.start_button = self._button(row, '▶ 송출 시작', self.start_server)
        self.start_button.setObjectName('primary')
        self.stop_button = self._button(row, '■ 중지', self.stop_server)
        self.stop_button.setEnabled(False)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(self.settings.port)
        row.addWidget(QLabel('포트'))
        row.addWidget(self.port)
        row.addStretch()
        card.addLayout(row)
        self.auto = QCheckBox('이 앱을 실행하면 송출 서버 자동 시작')
        self.auto.setChecked(self.settings.auto_start)
        self.auto.toggled.connect(self.save_controls)
        card.addWidget(self.auto)
        self.server_detail = QLabel('준비됨')
        self.server_detail.setWordWrap(True)
        card.addWidget(self.server_detail)

    def _build_audio(self):
        card = self._card('audio', '02  오디오 설정', '마스터 음소거 대신 가상 출력 장치를 사용하면 PC 스피커와 송출을 분리할 수 있습니다.')
        row = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setMinimumContentsLength(16)
        self.devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.devices.currentIndexChanged.connect(self.select_device)
        row.addWidget(self.devices, 1)
        self._button(row, '새로고침', self.refresh_devices)
        card.addLayout(row)
        self.virtual_status = QLabel('장치 확인 중…')
        card.addWidget(self.virtual_status)
        row = QHBoxLayout()
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 200)
        self.volume.setValue(round(self.settings.gain * 100))
        self.volume.valueChanged.connect(self.volume_changed)
        row.addWidget(QLabel('송출 음량'))
        row.addWidget(self.volume, 1)
        self.volume_text = QLabel(f'{self.volume.value()}%')
        row.addWidget(self.volume_text)
        self.mute = QCheckBox('음소거')
        self.mute.toggled.connect(lambda value: setattr(self.engine, 'muted', value))
        row.addWidget(self.mute)
        card.addLayout(row)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(10)
        self.level.setAccessibleName('실시간 오디오 입력 레벨')
        card.addWidget(self.level)
        self._button(card, 'PC 스피커 무음 설정 / VB-CABLE 설치 안내', self.install_driver)

    def _build_phone(self):
        card = self._card('phone', '03  휴대폰 연결', '휴대폰 브라우저에서 주소를 열고 PIN을 입력한 후 듣기 시작을 누르세요. QR에는 PIN이 포함되지 않습니다.')
        self.address = QLineEdit()
        addresses = lan_addresses()
        self.address.setText(addresses[0] if addresses else '')
        self.address.textChanged.connect(self.update_url)
        row = QHBoxLayout()
        row.addWidget(QLabel('LAN 주소'))
        row.addWidget(self.address, 1)
        card.addLayout(row)
        self.url_label = QLabel('서버를 시작하세요.')
        self.url_label.setWordWrap(True)
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card.addWidget(self.url_label)
        self.network_hint = QLabel('')
        self.network_hint.setWordWrap(True)
        card.addWidget(self.network_hint)
        self.qr = QLabel('서버를 시작하면 QR 코드가 표시됩니다.')
        self.qr.setFixedSize(256, 256)
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setWordWrap(True)
        self.qr.setStyleSheet('background: white; color: #25334a; border-radius: 12px;')
        card.addWidget(self.qr, alignment=Qt.AlignmentFlag.AlignHCenter)
        row = QHBoxLayout()
        self.pin_label = QLabel(f'접속 PIN  {self.runtime.pin}')
        self.pin_label.setObjectName('pin')
        row.addWidget(self.pin_label)
        row.addStretch()
        self._button(row, 'PIN 재생성', self.rotate_pin)
        self._button(row, '주소 복사', self.copy_url)
        card.addLayout(row)
        self.clients = QListWidget()
        self.clients.setMaximumHeight(150)
        self.clients.setMinimumHeight(70)
        card.addWidget(self.clients)
        self._button(card, '선택한 수신기 연결 해제', self.disconnect_client)
        caption = QLabel('이어폰은 휴대폰에 연결하세요. 화면 잠금·브라우저 백그라운드에서는 기기 정책에 따라 재생이 중단될 수 있습니다.')
        caption.setWordWrap(True)
        card.addWidget(caption)

    def _build_logs(self):
        card = self._card('logs', '04  로그 및 진단', '문제가 생기면 장치와 네트워크 상태를 확인하세요. 진단 정보에는 PIN과 토큰이 포함되지 않습니다.')
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMinimumHeight(140)
        self.logs.setMaximumHeight(220)
        card.addWidget(self.logs)
        row = QHBoxLayout()
        self._button(row, '로그 열기', self.open_log)
        self._button(row, '로그 저장', self.save_log)
        self._button(row, '진단 복사', self.copy_diagnostics)
        self.update_button = self._button(row, '업데이트 확인', self.manual_update)
        card.addLayout(row)

    def run_task(self, operation, callback=None):
        future = self.executor.submit(operation)
        def complete(result):
            try:
                self.bridge.done.emit(callback, result.result(), None)
            except Exception as error:
                try:
                    self.bridge.done.emit(callback, None, str(error))
                except RuntimeError:
                    pass
        future.add_done_callback(complete)

    def _finished(self, callback, result, error):
        if error:
            LOG.error('Desktop operation failed: %s', error)
            self.server_detail.setText(str(error))
            if not self.closing:
                QMessageBox.warning(self, '작업 실패', str(error))
        if callback:
            callback(result, error)

    def save_controls(self, *_):
        self.settings.auto_start = self.auto.isChecked()
        self.settings.port = self.port.value()
        self.settings.gain = self.volume.value() / 100
        try:
            self.settings.save()
        except OSError as error:
            self.server_detail.setText(f'설정 저장 실패: {error}')

    def start_server(self):
        if self.busy:
            return
        self.save_controls()
        self.busy = True
        self.start_button.setEnabled(False)
        self.server_detail.setText('서버 시작 중…')
        host, port = self.settings.host, self.settings.port
        cert, key = self.settings.tls_cert or None, self.settings.tls_key or None
        self._active_protocol = 'https' if cert and key else 'http'
        self._active_port = port
        self.run_task(lambda: self.runtime.start(host=host, port=port, cert=cert, key=key), self.server_finished)

    def stop_server(self):
        if self.busy:
            return
        self.busy = True
        self.stop_button.setEnabled(False)
        self.server_detail.setText('서버 중지 중…')
        self.run_task(self.runtime.stop, self.server_finished)

    def server_finished(self, result, error):
        self.busy = False
        self.refresh_status()
        self.update_url()

    def refresh_devices(self):
        def done(devices, error):
            if error:
                self.virtual_status.setText('오디오 장치를 확인하지 못했습니다. 새로고침으로 재시도하세요.')
                return
            self.devices.blockSignals(True)
            self.devices.clear()
            self.devices.addItem('시스템 기본 출력 장치 (자동 감지)', None)
            selected = 0
            virtual = False
            for device in devices:
                self.devices.addItem(device['name'], device['id'])
                virtual = virtual or device.get('virtual', False)
                if device['id'] == self.settings.device_id:
                    selected = self.devices.count() - 1
            self.devices.setCurrentIndex(selected)
            self.devices.blockSignals(False)
            self.virtual_status.setText('✓ 가상 오디오 장치 감지됨' if virtual else 'VB-CABLE 미감지 · 일반 출력 장치로도 시험할 수 있습니다.')
            if self.first_scan:
                self.first_scan = False
                if not virtual:
                    QTimer.singleShot(300, self.install_driver)
        self.run_task(self.engine.devices, done)

    def select_device(self, *_):
        self.settings.device_id = self.devices.currentData()
        self.engine.select(self.settings.device_id)
        self.save_controls()

    def volume_changed(self, value):
        self.engine.gain = value / 100
        self.volume_text.setText(f'{value}%')
        self.save_controls()

    def refresh_status(self):
        info = self.runtime.snapshot()
        running = info.get('running', False)
        clients = info.get('clients', [])
        self.state.setText(tr('● {state} · 수신기 {count}대', state=tr('송출 중' if running else '중지됨'), count=len(clients)))
        if not self.busy:
            self.start_button.setEnabled(not running)
            self.stop_button.setEnabled(running)
            self.port.setEnabled(not running)
            error = info.get('error') or self.engine.error
            self.server_detail.setText(str(error) if error else ('연결을 기다리고 있습니다.' if running else '준비됨 · 시작 버튼으로 송출하세요.'))
        self.level.setValue(min(100, max(0, round(self.engine.level * 100))))
        if clients != self.cached_clients:
            selected = self.clients.currentItem()
            selected_id = selected.data(Qt.ItemDataRole.UserRole) if selected else None
            self.clients.clear()
            for client in clients:
                item = QListWidgetItem(f'{client.get("address", "휴대폰")}  ·  {client.get("state", "연결됨")}')
                item.setData(Qt.ItemDataRole.UserRole, client['id'])
                self.clients.addItem(item)
                if client['id'] == selected_id:
                    self.clients.setCurrentItem(item)
            self.cached_clients = clients
        try:
            path = Path(log_path())
            with path.open('rb') as stream:
                stream.seek(max(0, path.stat().st_size - 20000))
                text = stream.read().decode('utf-8', errors='replace')
            if self.logs.toPlainText() != text:
                self.logs.setPlainText(text)
                self.logs.verticalScrollBar().setValue(self.logs.verticalScrollBar().maximum())
        except OSError:
            pass
        if running and not self._url:
            self.update_url()

    def update_url(self, *_):
        if not hasattr(self, 'qr'):
            return
        host = self.address.text().strip()
        try:
            parsed = ipaddress.ip_address(host)
            valid = parsed.version == 4 and parsed.is_private and not parsed.is_loopback and not parsed.is_unspecified
        except ValueError:
            valid = False
        if not valid:
            self._url = ''
            self.url_label.setText('휴대폰에서 접속할 PC의 LAN IPv4 주소를 선택하세요.')
            self.network_hint.setText('유효한 사설 LAN 주소가 없습니다. Wi-Fi 연결을 확인하거나 LAN 주소를 직접 입력하세요.')
            self.qr.clear()
            self.qr.setText('LAN 주소를 확인하세요.')
            return
        running = self.runtime.snapshot().get('running', False)
        if not running:
            self._url = ''
            self.url_label.setText('서버를 시작하면 접속 주소가 표시됩니다.')
            self.qr.clear()
            self.qr.setText('서버를 시작하세요.')
            return
        protocol = self._active_protocol
        url = f'{protocol}://{host}:{self._active_port}/'
        self.url_label.setText(url)
        self.network_hint.setText('같은 Wi-Fi에서 사용하세요. 방화벽은 개인 네트워크만 허용하세요. ' +
            ('휴대폰에서 신뢰하는 인증서가 필요합니다.' if protocol == 'https' else 'HTTP에서는 PIN·인증정보가 LAN에 노출될 수 있습니다. 설정에서 HTTPS를 구성하세요.'))
        if url == self._url:
            return
        self._url = url
        code = qrcode.QRCode(border=4, box_size=8)
        code.add_data(url)
        code.make(fit=True)
        image = code.make_image(fill_color='black', back_color='white').convert('RGB')
        raw = image.tobytes('raw', 'RGB')
        qt_image = QImage(raw, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy()
        self.qr.setPixmap(QPixmap.fromImage(qt_image).scaled(248, 248, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))

    def copy_url(self):
        if self._url:
            QApplication.clipboard().setText(self._url)

    def rotate_pin(self):
        self.run_task(self.runtime.rotate_pin, lambda pin, error: self.pin_label.setText(f'접속 PIN  {pin}') if not error else None)

    def disconnect_client(self):
        item = self.clients.currentItem()
        if item:
            self.run_task(lambda: self.runtime.disconnect(item.data(Qt.ItemDataRole.UserRole)))

    def install_driver(self):
        from .installer import install_vbcable
        install_vbcable(self)

    def automatic_update(self):
        if not self.settings.check_updates:
            return
        from .updater import check_for_update
        check_for_update(self, silent=True)

    def manual_update(self):
        from .updater import check_for_update
        check_for_update(self)

    def open_log(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path())))

    def save_log(self):
        name, _ = QFileDialog.getSaveFileName(self, '로그 저장', 'AirEar.log', '로그 (*.log)', options=QFileDialog.Option.DontUseNativeDialog)
        if name:
            try:
                Path(name).write_bytes(Path(log_path()).read_bytes())
            except OSError as error:
                QMessageBox.warning(self, '저장 실패', str(error))

    def copy_diagnostics(self):
        info = self.runtime.snapshot()
        diagnostics = {
            'version': '1.0.4', 'running': info.get('running'),
            'receiver_count': len(info.get('clients', [])),
            'port': self.settings.port, 'tls': bool(self.settings.tls_cert),
            'gain': self.engine.gain, 'muted': self.engine.muted,
            'device_id': self.settings.device_id, 'audio_level': self.engine.level,
            'audio_buffer': self.engine.metrics() if hasattr(self.engine, 'metrics') else {},
        }
        QApplication.clipboard().setText(json.dumps(diagnostics, ensure_ascii=False, indent=2))

    def edit_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('AirEar 설정')
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        language = QComboBox()
        for locale in available_languages():
            language.addItem(locale["name"], locale["code"])
        language.setCurrentIndex(max(0, language.findData(self.settings.language)))
        language.currentIndexChanged.connect(lambda _: self.change_language(language.currentData()))
        form.addRow("언어", language)
        language_folder = QPushButton("언어 파일 폴더 열기")
        def open_languages():
            from .paths import data_dir
            folder = data_dir() / "languages"
            folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        language_folder.clicked.connect(open_languages)
        form.addRow(language_folder)
        form.addRow(QLabel("언어 파일은 저장 즉시 반영됩니다."))
        theme = QComboBox()
        for label, value in [('시스템 자동', 'system'), ('밝게', 'light'), ('어둡게', 'dark')]:
            theme.addItem(label, value)
        theme.setCurrentIndex(max(0, theme.findData(self.settings.theme)))
        cert = QLineEdit(self.settings.tls_cert)
        key = QLineEdit(self.settings.tls_key)
        host = QLineEdit(self.settings.host)
        update = QCheckBox('실행 시 GitHub Releases 업데이트 확인')
        update.setChecked(self.settings.check_updates)
        form.addRow('테마', theme)
        form.addRow('바인딩 주소', host)
        form.addRow('HTTPS 인증서 PEM', cert)
        form.addRow('HTTPS 개인 키 PEM', key)
        form.addRow(update)
        layout.addLayout(form)
        hint = QLabel('주소·HTTPS 변경은 서버 재시작 후 적용됩니다.\n개인 키는 PC에 보관하세요. 휴대폰에서 신뢰하는 인증서가 필요합니다.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if bool(cert.text().strip()) != bool(key.text().strip()):
                QMessageBox.warning(self, 'HTTPS 설정', '인증서와 개인 키를 함께 지정하세요.')
                return
            self.settings.theme = theme.currentData()
            self.settings.host = host.text().strip() or '0.0.0.0'
            self.settings.tls_cert = cert.text().strip()
            self.settings.tls_key = key.text().strip()
            self.settings.check_updates = update.isChecked()
            self.save_controls()
            self.apply_theme()

    def apply_theme(self):
        dark = self.settings.theme == 'dark' or (self.settings.theme == 'system' and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        colors = dict(bg='#11151d', panel='#191f2a', text='#e9eef8', muted='#99a7bc', line='#2d384b', field='#202938') if dark else dict(bg='#f3f6fb', panel='#ffffff', text='#1c2b43', muted='#65748b', line='#dce4f0', field='#f3f6fb')
        self.setStyleSheet('''
            QWidget {{background:{bg};color:{text};font-family:'Segoe UI','Malgun Gothic';font-size:13px;}}
            #sidebar {{background:{panel};border-right:1px solid {line};}}
            #sidebar QLabel {{background:transparent;}}
            #brand {{font-size:28px;font-weight:700;color:#4e91ff;}}
            #heading {{font-size:19px;font-weight:650;}}
            #card {{background:{panel};border:1px solid {line};border-radius:14px;}}
            #card QLabel,#card QCheckBox {{background:transparent;}}
            #cardTitle {{font-size:18px;font-weight:650;}}
            #muted {{color:{muted};margin-bottom:10px;}}
            #pin {{font-size:20px;font-weight:700;color:#4e91ff;}}
            QPushButton {{background:{field};border:1px solid {line};border-radius:7px;padding:9px 12px;}}
            QPushButton:hover {{border-color:#4e91ff;}}
            QPushButton:disabled {{color:{muted};}}
            QPushButton#primary {{background:#2776e8;border-color:#2776e8;color:white;font-weight:650;}}
            QLineEdit,QComboBox,QSpinBox,QTextEdit,QListWidget {{background:{field};border:1px solid {line};border-radius:7px;padding:7px;}}
            QProgressBar {{background:{field};border:0;border-radius:5px;}}
            QProgressBar::chunk {{background:#3889f4;border-radius:5px;}}
            QScrollArea {{border:0;}}
            QSlider::groove:horizontal {{height:5px;background:{line};border-radius:2px;}}
            QSlider::handle:horizontal {{width:17px;margin:-6px 0;background:#3889f4;border-radius:8px;}}
        '''.format(**colors))

    def resizeEvent(self, event):
        self.sidebar.setVisible(self.width() >= 800)
        super().resizeEvent(event)

    def closeEvent(self, event):
        if self.closing:
            event.accept()
            return
        event.ignore()
        if self.busy:
            QMessageBox.information(self, '작업 진행 중', '서버 시작·중지가 끝난 뒤 창을 닫아 주세요.')
            return
        self.closing = True
        self.timer.stop()
        self.update_timer.stop()
        self.save_controls()
        self.setEnabled(False)
        def stopped(result, error):
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.close()
        self.run_task(self.runtime.stop, stopped)
