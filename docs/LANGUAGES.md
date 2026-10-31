# Language files / 언어 파일

AirEar includes Korean (`ko`) and English (`en`). Desktop and phone receiver text live in JSON files rather than being embedded in the executable's UI code. Choose the desktop language in **Settings → Language**, or use the language selector on the phone's receiver page. The phone remembers its own selection, so receivers can use different languages.

한국어와 영어를 기본 제공하며, PC는 **설정 → 언어**, 휴대폰은 수신 페이지의 언어 선택에서 바꿉니다. PC와 휴대폰의 언어는 각각 선택할 수 있습니다.

## File locations

| Location | Purpose |
|---|---|
| `src/airear/languages/ko.json` | Built-in Korean pack |
| `src/airear/languages/en.json` | Built-in English pack |
| `%LOCALAPPDATA%\AirEar\languages\<code>.json` | User additions and overrides; survives EXE updates |

Pack filenames use language codes, for example `ko.json`, `en.json`, or `ja.json`. Codes may contain letters, numbers, `_`, and `-`. Save files as **UTF-8 JSON**.

사용자 언어 파일은 `%LOCALAPPDATA%\AirEar\languages`에 보관합니다. EXE 내부 파일을 수정할 필요가 없으며 프로그램 업데이트 후에도 사용자 파일을 유지할 수 있습니다.

## JSON structure

```json
{
  "name": "English",
  "strings": {
    "서버 관리": "Server",
    "설정": "Settings",
    "종료": "Quit"
  },
  "web": {
    "language": "Language",
    "pin_placeholder": "Enter the PIN shown on the PC"
  }
}
```

- `name` is the language's display name in selectors.
- `strings` contains desktop text. Keys match the original source text exactly, including spaces, punctuation, and line breaks. Desktop keys remain stable source identifiers even when the currently displayed language is different.
- `web` contains the receiver page's named message keys. Use the included English or Korean file as the complete reference; the short example above is only a format example.
- Values must be strings. Keep any placeholders such as `{name}`, `{count}`, or `{attempt}` unchanged in the translated value.
- JSON uses double quotes. Escape a literal line break as `\n`; do not add comments or trailing commas.

`name`은 언어 선택 목록의 표시명입니다. `strings`는 PC 화면 문구, `web`은 휴대폰 수신 화면 문구입니다. 기본 파일의 키를 그대로 유지하고 값만 번역하세요. `{count}` 같은 치환 변수는 삭제하거나 이름을 바꾸지 마세요.

## Override a few words

Create `%LOCALAPPDATA%\AirEar\languages\en.json` and include only the text you want to override. User entries are merged over the bundled `en.json`; other built-in translations remain available. For example, change the desktop Quit command:

```json
{
  "name": "English",
  "strings": {
    "종료": "Exit AirEar"
  }
}
```

실행 중인 언어 파일을 저장하면 PC 화면과 연결된 수신 페이지가 주기적으로 다시 읽어 번역을 적용합니다. 언어 파일 편집을 위해 송출 서버나 EXE를 다시 시작할 필요는 없습니다. 파일이 잘못된 JSON이면 로그를 확인하고 마지막 정상 파일 또는 기본 파일로 되돌리세요.

## Add another language

1. Copy the complete bundled `en.json` to the user language folder, for example as `ja.json`.
2. Change `name` to the language's native display name.
3. Translate the values under both `strings` and `web`; preserve all keys and placeholders.
4. Save the file, then reopen the desktop settings dialog to refresh the language list. Reload an already-open phone page to discover a newly added language.
5. Select the new language. Further edits to that selected file reload while the app and page are running.
6. Check compact windows, dialogs, tray commands, status messages, and the phone page. Long translations should still fit or wrap naturally.

새 언어를 추가할 때는 기본 영어 파일 전체를 복사하는 방식이 가장 편리합니다. 새 파일을 목록에서 찾으려면 PC 설정 창을 다시 열고, 휴대폰에서는 페이지를 새로고침하세요. 이미 선택된 언어 파일의 문구 수정은 실행 중 적용됩니다.

## Scope and fallback

Translate all bundled keys to keep the interface consistent. Missing desktop entries fall back to the source text; missing receiver entries fall back to English. Device names, user-entered addresses, filenames, and diagnostic data are preserved rather than translated. Error details supplied directly by Windows, drivers, or third-party libraries may be shown in the language used by those components.

기본 문구가 빠져 있으면 PC는 원문, 수신 페이지는 영어로 표시될 수 있습니다. 오디오 장치 이름, 사용자가 입력한 주소, 파일명, 진단 데이터는 번역하지 않습니다. 윈도우·드라이버·외부 라이브러리가 직접 제공하는 오류 상세는 해당 구성요소의 언어로 나타날 수 있습니다.
