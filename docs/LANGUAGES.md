# Language files

AirEar ships with Korean, English, and Japanese JSON files in `languages/`. On first launch, the app copies them to:

```text
%LOCALAPPDATA%\AirEar\languages\ko.json
%LOCALAPPDATA%\AirEar\languages\en.json
%LOCALAPPDATA%\AirEar\languages\ja.json
```

The desktop screen reads the selected JSON file again every 2.5 seconds. The phone page checks its selected file every 3 seconds. Save a valid JSON file to apply text changes without restarting the app or reloading the phone page.

## Add a language

1. Copy `en.json` to a new locale file, for example `fr.json`.
2. Translate the existing values and keep the same nested keys.
3. Add the locale code and display name to the language selector in `electron/desktop/index.html` and `electron/phone/index.html`.
4. Add the locale code to the allowlists in `electron/main.cjs` and `electron/server.cjs`.
5. Add matching app-side defaults under `languages/` so new installations receive the file.
6. Validate JSON syntax and ensure each key referenced by `data-i18n` or `textFor()` exists.

Do not place HTML or executable code in translation files. Values are rendered as text. The selected language is stored in `%LOCALAPPDATA%\AirEar\settings.json` for the desktop app; the phone page defaults from the browser's preferred language.
