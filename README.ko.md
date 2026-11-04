# AirEar

AirEar는 Windows에서 재생되는 시스템 오디오를 같은 개인 Wi-Fi의 휴대폰 브라우저로 실시간 전송합니다. 카페나 도서관에서도 이어폰을 휴대폰에 연결해 둔 채 PC 소리를 들을 수 있어, 이어폰을 PC와 휴대폰 사이에서 번갈아 연결할 필요가 없습니다.

[English README](README.md) · [설치 안내](docs/INSTALL.md) · [문제 해결](docs/TROUBLESHOOTING.md) · [언어 파일 안내](docs/LANGUAGES.md)

## 동작 방식

```text
Windows 시스템 오디오 → Electron 루프백 캡처 → WebRTC/Opus → 휴대폰 브라우저
```

휴대폰에 앱을 설치할 필요가 없습니다. Safari, Chrome 등 모바일 브라우저에서 LAN 주소를 열고 AirEar에 표시된 PIN을 입력한 뒤 **연결하고 듣기**를 누르세요. AirPods 등 Bluetooth 이어폰은 휴대폰에 연결한 상태로 사용할 수 있습니다.

## 설치

1. [GitHub Releases](https://github.com/mycodehive/airear/releases)에서 최신 **AirEar-Setup-x64.exe**를 받습니다.
2. 사용자별 설치 프로그램을 실행합니다. 기본적으로 관리자 권한을 요구하지 않습니다.
3. AirEar를 실행합니다. 현재 설치 파일은 코드 서명되지 않아 Windows SmartScreen 경고가 나타날 수 있습니다.
4. 앱은 실행 시와 4시간마다 GitHub Releases 업데이트를 확인합니다. 업데이트 다운로드는 사용자가 업데이트 버튼을 눌렀을 때 시작합니다.

Electron 설치 프로그램은 기존 Python `AirEar.exe`와 설치 방식이 다릅니다. 기존 버전에서 옮길 때는 프로그램을 종료하고 새 설치 프로그램을 한 번 실행하세요. `%LOCALAPPDATA%\AirEar\settings.json`의 호환되는 설정은 불러옵니다.

## 휴대폰 연결

1. PC와 휴대폰을 같은 신뢰할 수 있는 Wi-Fi에 연결합니다.
2. AirEar에서 출력 장치를 선택합니다. **송출 시작**을 누르면 `CABLE Input (VB-Audio Virtual Cable)`이 있으면 자동으로 선택하고, 없으면 앱에서 선택한 장치나 기본 출력 장치를 사용합니다.
3. 휴대폰으로 QR을 스캔하거나 화면의 LAN 주소를 엽니다.
4. 데스크톱 앱의 8자리 PIN을 입력하고 **연결하고 듣기**를 누릅니다.
5. 듣기 음량은 휴대폰 버튼으로 조절하고, 송출 음량은 AirEar 슬라이더로 조절합니다.

PC 스피커로 소리를 내지 않으려면 [VB-Audio 공식 사이트](https://vb-audio.com/Cable/)에서 VB-CABLE을 설치하고 Windows 소리 설정에서 재생을 `CABLE Input`으로 보내세요. AirEar가 해당 장치를 캡처해 휴대폰으로 송출합니다. AirEar는 오디오 드라이버를 동의 없이 다운로드하거나 설치하지 않습니다. 자세한 내용은 [설치 안내](docs/INSTALL.md)를 참고하세요.

## 현재 오디오 캡처 범위

Windows에서는 AirEar가 WASAPI 루프백을 지원하는 출력 장치를 나열하고 선택한 장치를 캡처합니다. 송출 시작 시 `CABLE Input (VB-Audio Virtual Cable)`이 있으면 우선 자동 선택합니다. 해당 루프백 신호에 원하는 오디오가 들어오도록 Windows 재생도 `CABLE Input`으로 보내야 합니다. AirEar의 선택은 캡처할 장치를 지정하며 Windows 전체의 기본 재생 장치를 변경하지 않습니다.

휴대폰에서는 사용자가 시작 동작을 한 뒤 HTML 오디오 플레이어로 재생합니다. 화면 잠금 상태의 재생은 휴대폰 운영체제와 브라우저에 따라 달라 보장되지 않습니다. 실제 Windows 장치에서 캡처와 장시간 재생을 검증해야 합니다.

## 다국어

한국어·영어·일본어 JSON 파일은 `%LOCALAPPDATA%\AirEar\languages`에 생성됩니다. JSON 값을 수정하면 데스크톱 화면은 자동으로 다시 읽고, 휴대폰 화면도 열려 있는 동안 선택한 언어 파일을 주기적으로 다시 읽습니다. 언어를 추가하는 방법은 [docs/LANGUAGES.md](docs/LANGUAGES.md)를 확인하세요.

## 개발

- 화면: HTML/CSS
- 화면 동작·시그널링·WebRTC·설정·번역: JavaScript
- 데스크톱 실행 및 Windows 시스템 루프백 오디오: Electron 45 + Node.js 24
- LAN 시그널링 및 휴대폰 화면: Express + WebSocket
- Windows x64 설치본: `electron-builder` + NSIS
- 자동 빌드: GitHub Actions 정적 검사, 테스트, Windows 설치·실행 스모크 검사, SHA256 생성

```sh
npm ci
npm run lint
npm test
npm start
```

Windows 설치 프로그램은 Windows에서 `npm run dist:win`으로 빌드합니다. [개발 안내](docs/DEVELOPMENT.md)와 [릴리스 안내](docs/RELEASING.md)를 참고하세요.

## 네트워크 및 개인정보

서버는 로컬 네트워크 인터페이스에 바인딩하고 사설 IPv4 LAN 클라이언트만 허용합니다. PIN 입력은 횟수 제한이 적용됩니다. HTTP 시그널링은 암호화되지 않으므로 신뢰할 수 있는 개인 네트워크에서만 사용하고 인터넷에 포트를 공개하지 마세요. WebRTC 미디어는 DTLS-SRTP로 암호화되지만 별도 HTTP 시그널링까지 암호화되는 것은 아닙니다.

## 코드 서명

현재 앱은 코드 서명 인증서 없이 배포됩니다. Windows SmartScreen 경고가 나타날 수 있습니다. 설치 전 소스와 릴리스에 첨부된 SHA256 체크섬을 확인하세요.
