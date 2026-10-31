# 검증 현황

기록일: 2026-10-31. 구현 버전: 1.0.0 후보. 환경: Linux x64 / Python3.12.14 / Qt offscreen. 실제 Windows와 iPhone은 사용할 수 없었습니다.

## 실행 완료

| 검사 | 결과 | 범위 |
|---|---|---|
| `uv sync --locked --extra dev` | 통과 | Linux 의존성 설치. Windows wheel 실행 검증은 아님 |
| `ruff check .` | 통과 | Python 정적 오류 검사 |
| `pytest -q` | **47 passed** | 아래 세부 범위 |
| `node --check src/airear/web/app.js` | 통과 | JavaScript 문법. Safari 실기기 테스트 아님 |
| `QT_QPA_PLATFORM=offscreen ... python -m airear --smoke-test` | 통과 | 소스 Qt/import/웹자산 존재. frozen EXE 아님 |
| GUI 이미지 검사 | 완료 | dark 카드·사이드바·QR·스크롤 위치. Linux에 한글 글꼴이 없어 Windows의 맑은 고딕 표시 자체는 미검증 |

일반 Linux GUI 실행은 xcb 라이브러리/디스플레이가 없어 실행 불가였습니다. 위 smoke는 명시적 offscreen 플랫폼에서 성공했습니다. Windows 실행 성공으로 대체하지 않습니다.

### 테스트 구성

- 오디오 12개: gain/peak limiter, silence/timestamp, bounded queue, resampling, surround center downmix, track restart, mock PortAudio callback/cleanup, 기본/선택 장치 변경, 연결 해제/동일 이름 재연결, 잘못 재사용된 index 거부.
- 서버 20개: LAN 판정, PIN, origin/token/expiry/한도, JSON 오류, PIN 회전, 관리자 HTTP 경로 부재, 인증정보 미로깅, 실제 aiortc끼리 Opus 프레임 수신·peer 정리, 실제 background aiohttp Runtime start/rotate/stop. ICE는 loopback으로 제한하여 외부 인터페이스 의존성을 제거했습니다.
- GUI 4개: 실제 Qt subprocess, 배율100/125/150/200%, 각 light/dark와 작은480×420창, QR256×256 전체 viewport 표시와 스크롤, 업데이트 timer/번역 fallback.
- 도우미 11개: 공식 다운로드 링크 추출, 허용 HTTPS host, ZIP 경로탈출 거부, 예상 EXE, settings roundtrip/corruption, release 자산·버전, checksum 불일치 삭제, 설치 거부 시 다운로드 미실행.

## 미검증 — 수락 전 필수

- [ ] GitHub push 및 PR 생성
- [ ] Windows Actions 의존성 설치·정적분석·테스트 통과
- [ ] PyInstaller Windows onefile 실제 생성
- [ ] AMD64 PE signature/PE32+ 및 frozen EXE smoke 통과
- [ ] GitHub Release에서 실제 EXE/체크섬 다운로드
- [ ] Python 미설치 Windows10/11 x64에서 GUI 실행
- [ ] Windows DPI100/125/150/200 및 실제 한글 폰트·테마 확인
- [ ] 실제 WASAPI 스피커 loopback 캡처
- [ ] 실제 VB-CABLE capture와 물리 스피커 무음 분리
- [ ] 실제 기본 장치 변경·unplug/replug·고샘플레이트·무음 유지
- [ ] iPhone Safari PIN/QR/명시적 재생/독립 음량
- [ ] 여러 iPhone 및 AirPods
- [ ] Safari Wi-Fi 끊김·재연결·iOS 잠금 후 재생 재개 안내
- [ ] HTTPS IP SAN/내부CA 신뢰 및 TLS 접속
- [ ] VB-CABLE 실제 동의/UAC 취소/설치 실패/성공 감지·재부팅
- [ ] 30분 이상 연속 스트리밍 및 CPU/RAM 기록
- [ ] 실제 종단간 평균/최대 지연·끊김 측정
- [ ] Windows frozen EXE 업데이트 적용·실패 rollback

측정표(미측정):

| Windows/출력장치 | iPhone/iOS | Wi-Fi | 수신기 수 | 재생시간 | 평균/최대지연 | 끊김 | CPU/RAM |
|---|---|---|---|---|---|---|---|
| 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 |

## 원격 작업 차단 근거

- GitHub connector `get_repo`, `fetch`, `list_installations`: `Unknown tool` 오류.
- `git clone`/읽기는 가능, `git push -u origin feat/airear-windows-webrtc`: `could not read Username for 'https://github.com': No such device or address`.
- API 비인증 조회는 rate limit에 걸렸으며 쓰기 인증을 대신하지 않습니다.

따라서 PR, Actions run ID, Release URL, 실제 Windows EXE를 생성했다고 보고하지 않습니다. 연결 복구 후 RELEASING.md의 절차를 실행해야 합니다.
