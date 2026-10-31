# 개발 진행 기록

원본 main: `1bbabd2` (README만 존재). 작업 브랜치: `feat/airear-windows-webrtc`.

| 단계 | 구현 파일 | 검증·상태 |
|---|---|---|
| 1 저장소·아키텍처 | pyproject.toml, uv.lock, settings/paths/entrypoint | lock 설치·설정 저장/복구 테스트. 최초 foundation commit062da72 |
| 2 GUI | gui.py, assets, test_gui.py | Qt offscreen100/125/150/200%, light/dark, QR 전체 표시 통과 |
| 3 오디오 | audio.py, test_audio.py | 합성/모의 WASAPI12개 통과. 실기기 미검증 |
| 4 WebRTC | server.py, web/, test_server.py |20개 통과. 실제 aiortc 간 Opus 프레임 수신. Safari 미검증 |
| 5 설치 도우미 | installer.py, downloads.py | consent 거부/ZIP/링크 검증. 실제 UAC·서명·설치 미검증 |
| 6 EXE | spec, launcher.py, build.ps1, version_info | 구성 완료. Linux에서 Windows EXE 생성·실행 불가 |
| 7 CI/CD | windows.yml | 구성 완료. 원격 push 인증 실패로 Actions 미실행 |
| 8 품질·문서·업데이트 | updater.py, README, docs/, test_helpers.py | 전체47테스트·Ruff·JS문법·소스 offscreen smoke 통과. 실제 자동교체 미검증 |

독립 커밋을 architecture / audio / server / GUI / installer+updater / build+docs로 구분했습니다. 정확한 SHA는 `git log --oneline`에 보존됩니다. GitHub 원격 PR은 인증 문제로 생성하지 못했습니다. 구현은 git bundle에도 보존하여 인증 복구 후 동일 커밋을 push할 수 있습니다.

## 기술 선택

- PyAudioWPatch의 WASAPI loopback API를 사용합니다. 일반 PyAudio의 loopback 지원을 가정하지 않습니다.
- aiohttp는 aiortc와 동일 asyncio loop에서 운용합니다. GUI thread와 분리합니다.
- unbuffered MediaRelay와 bounded capture queue,48k/20ms clock으로 오래된 프레임 누적을 제한합니다.
- iOS에서 HTMLAudio.volume 지원을 가정하지 않고 사용자의 동작으로 resume한 WebAudio gain을 사용합니다.
- 공식 VB-CABLE 링크를 페이지에서 찾고 서명 검증 후 공식 interactive installer만 엽니다. silent install의 성공을 가정하지 않습니다.
- hardware 미검증 후보는 tag workflow에서 prerelease로만 게시합니다. 정식 승격은 수락 결과 기록 뒤 수행합니다.

## 남은 기능 한계

- 영어 UI는 핵심 문자열 확장 구조만 있으며 전체 번역은 미완료입니다.
- 현재 출력 장치 이름은 실행 중 재연결에서 보호합니다. 재부팅 후 Windows endpoint index가 바뀐 경우 UI에서 장치를 다시 선택하세요.
- 화면 잠금/백그라운드 유지, 측정 전 지연 수치는 보장하지 않습니다.
- 코드 서명, 오프라인 서명키 업데이트, 인터넷 원격 접속은 구현하지 않았습니다.
