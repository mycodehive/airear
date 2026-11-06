'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { TextDecoder } = require('node:util');

const SUPPORTED_LANGUAGES = new Set(['ko', 'en', 'ja']);
const UTF8 = new TextDecoder('utf-8', { fatal: true });

function readJson(file) {
  try {
    const text = UTF8.decode(fs.readFileSync(file));
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isCorruptedText(value) {
  return value.includes('\uFFFD') || /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(value) || /(?:ì|ë|ê|Ã|Â)[\u0080-\uFFFF]/u.test(value);
}

function mergePack(defaults, overrides) {
  if (!defaults || typeof defaults !== 'object' || Array.isArray(defaults)) return overrides ?? defaults;
  const result = { ...defaults };
  if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides)) return result;
  for (const [key, baseValue] of Object.entries(defaults)) {
    const customValue = overrides[key];
    if (baseValue && typeof baseValue === 'object' && !Array.isArray(baseValue)) {
      result[key] = mergePack(baseValue, customValue);
    } else if (typeof baseValue === 'string' && typeof customValue === 'string' && !isCorruptedText(customValue)) {
      result[key] = customValue;
    }
  }
  for (const [key, value] of Object.entries(overrides)) {
    if (!(key in result) && typeof value === 'string' && !isCorruptedText(value)) result[key] = value;
  }
  return result;
}

function readLanguagePack(language, { userRoot, bundledRoot }) {
  const selected = SUPPORTED_LANGUAGES.has(language) ? language : 'ko';
  const english = readJson(path.join(bundledRoot, 'en.json')) || {};
  const bundled = readJson(path.join(bundledRoot, `${selected}.json`)) || english;
  const user = userRoot ? readJson(path.join(userRoot, `${selected}.json`)) : null;
  return mergePack(mergePack(english, bundled), user);
}

function repairLanguageFiles({ userRoot, bundledRoot }) {
  fs.mkdirSync(userRoot, { recursive: true });
  for (const language of SUPPORTED_LANGUAGES) {
    const repaired = readLanguagePack(language, { userRoot, bundledRoot });
    fs.writeFileSync(path.join(userRoot, `${language}.json`), `${JSON.stringify(repaired, null, 2)}\n`, 'utf8');
  }
}

module.exports = { SUPPORTED_LANGUAGES, readLanguagePack, repairLanguageFiles };
