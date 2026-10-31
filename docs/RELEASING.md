# GitHub 반영과 릴리스

이 세션에서는 GitHub 플러그인 `Unknown tool` 오류와 Git push 인증 부재로 원격 반영을 완료하지 못했습니다. 로컬 구현/테스트 결과는 VALIDATION.md 참조.

1. GitHub 쓰기 권한이 있는 인증 환경에서 저장소를 열고 제공된 Git bundle 브랜치를 가져오거나 소스를 적용합니다.
2. `feat/airear-windows-webrtc`를 push하고 main 대상 PR을 엽니다. 단계별 커밋 이력은 DEVELOPMENT.md 참조.
3. Windows EXE workflow를 실행합니다. 실패한 job 로그를 확인하고 수정하여 다시 통과시킵니다. 이 단계는 현재 미실행입니다.
4. artifacts의 실제 EXE와 체크섬을 내려받아 Python 없는 Windows10/11 x64에서 실행합니다.
5. VALIDATION.md의 실기기 항목을 채웁니다. `--smoke-test`는 Qt/의존성/웹자산 import 확인이며 오디오/Safari 실기기 검증이 아닙니다.
6. 검증용 `v1.0.0-rc.1` 태그를 push하면 Windows 빌드 통과 뒤 EXE/체크섬/노트가 prerelease로 게시됩니다.
7. 실기기 수락 완료 후 문서/버전을 일치시켜 `v1.0.0`을 만들고 검증 내용을 포함해 Release를 정식판으로 승격합니다. workflow는 실기기 검증 없는 정식 표시를 막기 위해 모든 태그를 기본 prerelease로 게시합니다.

PowerShell 예시(인증 완료 뒤):

```powershell
git clone https://github.com/mycodehive/airear.git
cd airear
git fetch ..\airear.bundle feat/airear-windows-webrtc:feat/airear-windows-webrtc
git switch feat/airear-windows-webrtc
git push -u origin feat/airear-windows-webrtc
# PR merge 및 Windows 검사 통과 뒤 검증 태그 생성
# git tag v1.0.0-rc.1
# git push origin v1.0.0-rc.1
```

정식 버전 갱신 시 `pyproject.toml`, `src/airear/__init__.py`, GUI 표시버전, `scripts/version_info.txt`, 릴리스 노트/검증 문서를 함께 갱신하고 `uv lock`을 수행합니다. 앱 업데이트는 정식 stable Release만 검사합니다. 프로그램 파일을 Program Files 등 읽기 전용 경로에 두면 사용자 권한 자동교체가 실패할 수 있어 사용자 쓰기 가능한 폴더를 사용하세요. 실패 시 `.previous` 백업에서 복구를 시도합니다.
