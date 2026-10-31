# AirEar · Windows Audio → iPhone

Windows 10/11 x64 시스템 오디오를 WASAPI Loopback으로 캡처하여 같은 LAN의 iPhone Safari에 Opus/WebRTC로 전달하는 데스크톱 앱입니다. Moaham의 사이드바·카드 구성을 참고한 PySide6 UI를 제공합니다.

**현재 상태: 1.0.0 구현 후보. Windows EXE 빌드와 Windows/iPhone 실기기 검증은 아직 수행하지 않았습니다.** GitHub 플러그인 연결 오류 및 Git push 인증 부재로 이 작업 세션에서 원격 반영/Actions/Release를 실행하지 못했습니다. 이 문서는 다운로드 가능한 EXE가 이미 존재한다고 주장하지 않습니다. [검증 현황](docs/VALIDATION.md)을 확인하세요.

## 주요 기능

- 기본/선택 WASAPI 출력 장치 캡처, 변경·오류 재시도, surround→stereo downmix
- 48 kHz stereo 20 ms 프레임, 무음 유지, 한정된 버퍼, 0~200% 송출 gain와 peak limiter
- 최대 4대 iPhone, 수신기별 로컬 음량, QR, 8자리 PIN, 만료 세션 및 PIN 재생성
- 시스템/밝게/어둡게 테마, 작은 창 스크롤, 고해상도 QR, AppData 설정·회전 로그
- 동의 후 공식 페이지에서 VB-CABLE 다운로드, ZIP 안전성 및 Authenticode 발행자 확인, 공식 설치 화면 실행
- 실행 시 및 4시간마다 GitHub 정식 Release 업데이트 확인, 동의 후 EXE 다운로드·SHA256 검증·종료 후 교체

## 사용자 실행

Windows 빌드가 통과하고 Release 자산이 게시된 뒤 [Releases](https://github.com/mycodehive/airear/releases)에서 **WindowsAudio_iPhone.exe** 하나를 받습니다. Python 설치는 필요 없습니다. 드라이버는 EXE에 포함되지 않으며 VB-CABLE은 선택 설치입니다.

1. EXE를 실행하고 오디오 장치를 선택합니다.
2. 송출 시작. Windows 방화벽을 허용할 경우 **개인 네트워크** 범위만 허용합니다.
3. iPhone을 같은 Wi-Fi에 연결하고 QR 또는 표시된 LAN 주소를 Safari에서 엽니다.
4. 데스크톱에 표시된 PIN을 입력하고 **듣기 시작**을 누릅니다.
5. AirPods를 사용하려면 iPhone에 연결합니다.

[설치 안내](docs/INSTALL.md) · [문제 해결](docs/TROUBLESHOOTING.md) · [HTTPS/보안](docs/SECURITY.md)

## PC 스피커 무음 송출

Windows 설정 → 시스템 → 소리 → 출력에서 **CABLE Input (VB-Audio Virtual Cable)** 을 선택합니다. AirEar에서는 해당 장치의 loopback을 선택합니다. 물리적 스피커 대신 가상 출력으로 보내므로 PC 마스터 음소거에 의존하지 않습니다. 특정 앱이 자체 출력 장치를 고정했다면 그 앱도 CABLE Input으로 지정해야 합니다. Windows의 ‘이 장치로 듣기’는 끄세요.

일반 스피커 loopback을 선택하면 PC와 iPhone 양쪽에서 들리는 것이 정상입니다. 송출 gain/음소거는 Windows 시스템 음량을 변경하지 않습니다. 서버는 사용자의 기본 출력 장치를 임의로 바꾸지 않습니다.

## 개발 및 Windows 빌드

Python 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다. 개발 환경에서는 uv가 Python 3.12를 준비할 수 있습니다. 일반 사용자 EXE에는 해당 절차가 없습니다.

```powershell
uv sync --locked --extra dev --python 3.12
uv run --locked --extra dev python -m airear
./scripts/build.ps1
```

`uv.lock`은 전이 의존성과 wheel 해시까지 고정합니다. 빌드 스크립트는 Ruff → pytest → PyInstaller onefile → PE 헤더 → 실제 frozen EXE `--smoke-test` → SHA256 순으로 실행합니다. 결과: `dist/WindowsAudio_iPhone.exe`, `dist/SHA256SUMS.txt`.

Linux에서는 오디오 합성/인증/Qt offscreen 테스트만 가능합니다. Windows 장치를 대신 검증하지 않습니다.

```bash
uv sync --locked --extra dev
QT_QPA_PLATFORM=offscreen uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check .
```

## 구조

| 경로 | 역할 |
|---|---|
| `src/airear/gui.py` | Qt UI, worker 조정, QR, 진단 |
| `src/airear/audio.py` | WASAPI callback/재시도, 리샘플링, 연속 AudioStreamTrack |
| `src/airear/server.py` | aiohttp 인증·시그널링, aiortc PeerConnection, unbuffered MediaRelay |
| `src/airear/web/` | Safari 수신 화면, WebAudio gain, 재연결 |
| `src/airear/installer.py` | 동의 기반 공식 VB-CABLE 도우미 |
| `src/airear/updater.py` | GitHub 정식 Release 확인/검증/교체 |
| `WindowsAudio_iPhone.spec` | GUI/서버/정적파일/런타임을 단일 EXE에 포함 |
| `.github/workflows/windows.yml` | Windows CI와 태그 Release |

캡처는 별도 thread/PortAudio callback, 시그널링은 별도 asyncio thread, GUI 작업은 제한된 worker pool을 사용합니다. 네트워크 관리자 API는 없으며 송출 관리 권한은 로컬 GUI에만 있습니다. 한국어 기본이며 `Window._TEXT`/`Window.text()`로 영어 확장을 시작할 수 있습니다. 전체 영어 UI는 아직 완성되지 않았습니다.

## CI/CD와 릴리스

브랜치/PR/태그에서 Windows 빌드를 실행하고 artifact에 EXE와 체크섬을 보관합니다. `v*` 태그는 빌드 통과 후 Release를 **prerelease**로 게시합니다. 실기기 수락 테스트를 완료하기 전 정식판으로 표시하지 않도록 의도적으로 제한했습니다. [릴리스 절차](docs/RELEASING.md)에 따라 검증 기록을 남긴 뒤 정식판으로 승격합니다. 앱 자동 업데이트는 GitHub의 `releases/latest`를 사용해 **정식판만** 설치합니다.

코드 서명 인증서는 포함되지 않습니다. 자체 EXE는 서명되지 않은 상태로 배포되며 Windows SmartScreen 경고가 발생할 수 있습니다. SHA256은 파일 무결성 확인이며 발행자 인증을 대체하지 않습니다.

## 제한 사항

- 인터넷 공개/포트포워딩/원격 릴레이 용도가 아닙니다. STUN/TURN 외부 서비스를 사용하지 않습니다.
- 기본 HTTP는 PIN·토큰을 암호화하지 않습니다. 실사용에는 iPhone이 신뢰하는 인증서를 설정한 HTTPS를 권장합니다.
- iOS 화면 잠금/백그라운드/AirPlay 정책에 따라 재생이 중단될 수 있습니다. 지연시간을 보장하지 않습니다.
- VB-CABLE 설치 도우미는 서명을 검증하지 못하거나 패키지 구조가 바뀌면 자동 실행을 중단하고 공식 사이트 수동 설치를 안내합니다.
- Windows driver/UAC/실제 Safari/30분 연속재생/지연 측정은 현재 미검증입니다.

공식 참고: [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch), [aiortc](https://aiortc.readthedocs.io/en/latest/), [VB-CABLE](https://vb-audio.com/Cable/), [WebKit autoplay](https://webkit.org/blog/6784/new-video-policies-for-ios/).
