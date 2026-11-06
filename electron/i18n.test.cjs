'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { TextDecoder } = require('node:util');
const { readLanguagePack, repairLanguageFiles } = require('./i18n.cjs');

const projectRoot = path.join(__dirname, '..');
const bundledRoot = path.join(projectRoot, 'languages');

function temporaryPackDirectory() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'airear-language-'));
}

test('Korean language pack is valid UTF-8 and contains complete readable Hangul UI text', () => {
  const bytes = fs.readFileSync(path.join(bundledRoot, 'ko.json'));
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  const pack = JSON.parse(text);
  assert.match(pack.title, /[가-힣]/u);
  assert.equal(pack.nav.dashboard, '대시보드');
  assert.equal(pack.settings.title, '프로그램 설정');
  assert.equal(pack.settings.updateNow, '업데이트 상태');
  assert.equal(pack.footer.screen.includes('\uFFFD'), false);
  assert.equal(text.includes('ì'), false);
});

test('all desktop and phone translation references resolve in every shipped language', () => {
  const htmlFiles = [
    path.join(projectRoot, 'electron', 'desktop', 'index.html'),
    path.join(projectRoot, 'electron', 'phone', 'index.html'),
  ];
  const references = new Set();
  for (const file of htmlFiles) {
    const html = fs.readFileSync(file, 'utf8');
    for (const match of html.matchAll(/data-i18n="([^"]+)"/gu)) references.add(match[1]);
  }
  for (const language of ['ko', 'en', 'ja']) {
    const pack = readLanguagePack(language, { bundledRoot });
    for (const key of references) {
      const value = key.split('.').reduce((node, part) => node && node[part], pack);
      assert.equal(typeof value, 'string', `${language} is missing ${key}`);
      assert.notEqual(value, key, `${language} displays a translation key for ${key}`);
    }
  }
});

test('stale partial language files fall back to complete bundled Korean strings', () => {
  const userRoot = temporaryPackDirectory();
  try {
    fs.writeFileSync(path.join(userRoot, 'ko.json'), '{"nav":{"dashboard":"내 대시보드"}}', 'utf8');
    const pack = readLanguagePack('ko', { userRoot, bundledRoot });
    assert.equal(pack.nav.dashboard, '내 대시보드');
    assert.equal(pack.nav.settings, '설정');
    assert.equal(pack.settings.updateNow, '업데이트 상태');
  } finally {
    fs.rmSync(userRoot, { recursive: true, force: true });
  }
});

test('language pack reloads edited JSON and replaces corrupted strings with bundled text', () => {
  const userRoot = temporaryPackDirectory();
  try {
    const initial = JSON.parse(fs.readFileSync(path.join(bundledRoot, 'ko.json'), 'utf8'));
    initial.nav.dashboard = '개인화 대시보드';
    initial.nav.settings = '�ㅅ정';
    fs.writeFileSync(path.join(userRoot, 'ko.json'), JSON.stringify(initial), 'utf8');
    let pack = readLanguagePack('ko', { userRoot, bundledRoot });
    assert.equal(pack.nav.dashboard, '개인화 대시보드');
    assert.equal(pack.nav.settings, '설정');

    initial.nav.dashboard = '실시간 변경';
    fs.writeFileSync(path.join(userRoot, 'ko.json'), JSON.stringify(initial), 'utf8');
    pack = readLanguagePack('ko', { userRoot, bundledRoot });
    assert.equal(pack.nav.dashboard, '실시간 변경');
  } finally {
    fs.rmSync(userRoot, { recursive: true, force: true });
  }
});

test('startup repairs all editable language files while preserving valid overrides', () => {
  const userRoot = temporaryPackDirectory();
  try {
    fs.writeFileSync(path.join(userRoot, 'ko.json'), '{"title":"사용자 제목"}', 'utf8');
    repairLanguageFiles({ userRoot, bundledRoot });
    const repaired = JSON.parse(fs.readFileSync(path.join(userRoot, 'ko.json'), 'utf8'));
    assert.equal(repaired.title, '사용자 제목');
    assert.equal(repaired.settings.updateNow, '업데이트 상태');
    for (const language of ['ko', 'en', 'ja']) assert.ok(fs.existsSync(path.join(userRoot, `${language}.json`)));
  } finally {
    fs.rmSync(userRoot, { recursive: true, force: true });
  }
});
