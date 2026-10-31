# 설치·시작 안내

현재 개발 후보이며 Windows 빌드/실기기 수락 검증은 미완료입니다.

## Windows 10/11 x64

1. 게시된 GitHub Releases의 `AirEar.exe`를 사용자 쓰기 가능한 폴더에 저장합니다. Python 설치는 불필요합니다.
2. SHA256SUMS.txt를 받아 `Get-FileHash .\AirEar.exe -Algorithm SHA256` 결과와 비교합니다.
3. 서명되지 않은 EXE이므로 SmartScreen 경고가 나타날 수 있습니다. 배포 출처를 확인한 뒤 실행 여부를 판단하세요.
4. 설치 안내에서 VB-CABLE이 필요하면 ‘설치하기’를 선택합니다. ‘나중에 설치’·‘취소’는 다운로드/설치를 하지 않습니다.
5. 공식 설치 프로그램의 Install Driver를 직접 진행하고 필요 시 재부팅합니다. 프로그램을 열었다는 사실은 설치 성공을 의미하지 않습니다. 완료 후 AirEar 장치 새로고침에서 가상 장치 감지를 확인합니다.
6. PC 무음은 Windows 출력과 AirEar loopback을 CABLE Input으로 지정합니다. Windows ‘이 장치로 듣기’를 활성화하지 마세요.
7. 서버 시작, 개인 방화벽 허용, 같은 Wi-Fi의 Safari에서 QR 주소 접속, PIN, 듣기 시작.

## 파일 위치

사용자 설정과 로그: `%LOCALAPPDATA%\AirEar`.

EXE는 상시 관리자 권한을 요구하지 않습니다. 드라이버 실행에서만 UAC를 표시합니다. UAC 취소나 설치 실패 후 일반 스피커 loopback으로 계속 시험할 수 있습니다.

## Safari

수신 음량은 화면 slider(Web Audio gain)와 휴대폰 물리 음량으로 조절합니다. AirPods는 휴대폰에 연결합니다. 화면 잠금/다른 앱 전환 후 재생이 중단되면 Safari로 돌아와 듣기 시작을 다시 누릅니다. iOS 자체 정책에 따른 제한을 앱에서 보장할 수 없습니다.
