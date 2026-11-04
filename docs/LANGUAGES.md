# Language files

AirEar ships with Korean, English, and Japanese JSON files in `languages/`. On first launch, the app copies them to:

```text
%LOCALAPPDATA%\AirEar\languages\ko.json
%LOCALAPPDATA%\AirEar\languages\en.json
%LOCALAPPDATA%\AirEar\languages\ja.json
```

Language JSON files use UTF-8. The desktop screen reads the selected JSON file again every 2.5 seconds. The phone page checks its selected file every 3 seconds. Save a valid JSON file to apply text changes without restarting the app or reloading the phone page.

On startup, AirEar fills missing or outdated keys in the editable files from the shipped language packs. The English pack is the final fallback for untranslated keys. Invalid UTF-8, malformed JSON, replacement characters, and common mojibake patterns fall back to the packaged translation, so a stale or damaged pack does not show translation keys such as `settings.title` in the UI. Valid custom strings are preserved and applied live.

The automated checks validate that the Korean pack decodes as UTF-8, contains readable Hangul for core UI text, and provides every desktop and phone label in Korean, English, and Japanese.

## Add a language

1. Copy `en.json` to a new locale file, for example `fr.json`.
2. Translate the existing values and keep the same nested keys.
3. Add the locale code and display name to the language selector in `electron/desktop/index.html` and `electron/phone/index.html`.
4. Add the locale code to the allowlists in `electron/main.cjs` and `electron/server.cjs`.
5. Add matching app-side defaults under `languages/` so new installations receive the file.
6. Validate JSON syntax and ensure each key referenced by `data-i18n` or `textFor()` exists.

Do not place HTML or executable code in translation files. Values are rendered as text. The selected language is stored in `%LOCALAPPDATA%\AirEar\settings.json` for the desktop app; the phone page defaults from the browser's preferred language.
