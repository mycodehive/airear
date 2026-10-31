# AirEar 1.0.0 — 검증용 빌드

Windows 시스템 오디오 → 휴대폰 Safari 송출을 위한 PySide6 GUI, WASAPI loopback, aiortc Opus WebRTC, QR/PIN, VB-CABLE 동의 설치 도우미, 독립 gain 및 GitHub 업데이트를 구현했습니다.

**서명되지 않은 EXE**입니다. SmartScreen 경고가 발생할 수 있습니다. Python은 EXE에 포함되며 일반 사용자는 별도로 설치하지 않습니다. VB-CABLE 드라이버는 별도 선택 설치입니다.

이 릴리스는 prerelease입니다. 자동화된 빌드/테스트의 성공과 실제 Windows/휴대폰 수락 검증은 별개입니다. Windows 오디오 드라이버/UAC·Safari/AirPods·30분 연속 송출·실제 지연 측정은 `docs/VALIDATION.md`에 기록된 상태를 확인하세요. 확인되지 않은 항목은 지원 검증 완료로 간주하지 않습니다.

개인 LAN 전용이며 인터넷 공개를 지원하지 않습니다. 기본 HTTP의 인증정보 노출 가능성 및 HTTPS 설정 방법은 `docs/SECURITY.md`를 확인하세요. iOS 화면 잠금/백그라운드 재생 유지는 보장하지 않습니다.
