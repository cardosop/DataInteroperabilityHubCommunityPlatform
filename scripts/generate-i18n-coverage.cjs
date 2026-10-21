#!/usr/bin/env node
/**
 * P0-11 (close-oss-release-conditions, F-2) — i18n coverage generator.
 *
 * ZERO-dependency: reads the locale catalogs
 * (frontend/src/shared/i18n/locales/{en,es,fr}.ts) and writes the
 * canonical coverage snapshot at
 * frontend/src/shared/i18n/locales/coverage.json.
 *
 * Coverage semantics (the 280.C.1.1 contract, mirrored by
 * coverage.test.ts): a key counts as TRANSLATED when the locale value
 * differs from the English value; a key missing from the locale counts
 * as untranslated. The committed coverage.json must be reproducible by
 * this script — `--check` fails on any drift, so a stale snapshot
 * cannot pass (the 2026-05-15 snapshot said es 62.6% while the live
 * catalogs had moved on: the P0-11 root cause for regenerating rather
 * than hand-editing).
 *
 * Usage:
 *   node scripts/generate-i18n-coverage.cjs            # write coverage.json
 *   node scripts/generate-i18n-coverage.cjs --check    # exit 1 on drift
 *   node scripts/generate-i18n-coverage.cjs --report   # list untranslated keys
 */

'use strict';

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');
const LOCALES_DIR = path.join(REPO_ROOT, 'frontend/src/shared/i18n/locales');
const OUT = path.join(LOCALES_DIR, 'coverage.json');
const EN = 'en';
const TARGETS = ['es', 'fr'];

/** Strip `//` and `/* *\/` comments so comment prose can never leak
 * into the parsed catalogs or key lists (a comment quoting "No" was
 * counted as a cognate key — the parse must be comment-blind). */
function stripComments(text) {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/.*$/gm, '');
}

/** Parse a flat `Record<string, string>` object from a .ts locale file.
 * Handles double-quoted keys and double- or single-quoted string values
 * (escaped quotes preserved verbatim). Returns { key: value }. */
function parseCatalog(file) {
  const text = stripComments(fs.readFileSync(file, 'utf8'));
  const out = {};
  const re = /["']([^"']+)["']\s*:\s*(?:"([^"]*)"|'([^']*)')/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    out[m[1]] = m[2] !== undefined ? m[2] : m[3];
  }
  return out;
}

/** Parse a `export const X_KEYS: readonly string[] = [ 'a', 'b' ];`
 * array from a locale file. Returns Set<string>. */
function parseKeyList(file, constName) {
  const text = stripComments(fs.readFileSync(file, 'utf8'));
  const anchor = new RegExp(
    'export\\s+const\\s+' + constName + '\\s*:\\s*readonly\\s+string\\[\\]\\s*=\\s*\\[([\\s\\S]*?)\\]'
  );
  const m = text.match(anchor);
  const out = new Set();
  if (!m) return out;
  const keyRe = /["']([^"']+)["']/g;
  let km;
  while ((km = keyRe.exec(m[1])) !== null) {
    out.add(km[1]);
  }
  return out;
}

function measure(enCatalog, localeCatalog, cognates) {
  const enKeys = Object.keys(enCatalog);
  let untranslated = 0;
  const missing = [];
  const identical = [];
  for (const key of enKeys) {
    if (!(key in localeCatalog)) {
      untranslated += 1;
      missing.push(key);
    } else if (localeCatalog[key] === enCatalog[key] && !cognates.has(key)) {
      untranslated += 1;
      identical.push(key);
    }
  }
  const translated = enKeys.length - untranslated;
  const coveragePct = Math.round((translated / enKeys.length) * 1000) / 10;
  return { translated, untranslated, coveragePct, missing, identical };
}

function snapshot() {
  const enCatalog = parseCatalog(path.join(LOCALES_DIR, `${EN}.ts`));
  const locales = {};
  for (const locale of TARGETS) {
    const localeFile = path.join(LOCALES_DIR, `${locale}.ts`);
    const cognates = parseKeyList(localeFile, `${locale.toUpperCase()}_COGNATE_KEYS`);
    const m = measure(enCatalog, parseCatalog(localeFile), cognates);
    locales[locale] = {
      translated: m.translated,
      untranslated: m.untranslated,
      cognates: cognates.size,
      coverage_pct: m.coveragePct,
    };
  }
  return {
    generated: new Date().toISOString().slice(0, 10),
    total_keys: Object.keys(enCatalog).length,
    locales,
    threshold_90pct: TARGETS.every((l) => locales[l].coverage_pct >= 90),
  };
}

function report() {
  const enCatalog = parseCatalog(path.join(LOCALES_DIR, `${EN}.ts`));
  for (const locale of TARGETS) {
    const localeFile = path.join(LOCALES_DIR, `${locale}.ts`);
    const cognates = parseKeyList(localeFile, `${locale.toUpperCase()}_COGNATE_KEYS`);
    const m = measure(enCatalog, parseCatalog(localeFile), cognates);
    console.log(`${locale}: ${m.translated}/${Object.keys(enCatalog).length} translated (${m.coveragePct}%)`);
    for (const key of m.missing) console.log(`  MISSING  ${key}`);
    for (const key of m.identical) console.log(`  IDENTICAL ${key}`);
  }
}

const mode = process.argv.includes('--check') ? 'check' : process.argv.includes('--report') ? 'report' : 'write';

if (mode === 'report') {
  report();
  process.exit(0);
}

const snap = snapshot();
const payload = JSON.stringify(snap, null, 2) + '\n';

if (mode === 'check') {
  const committed = fs.readFileSync(OUT, 'utf8');
  if (committed === payload) {
    console.log('i18n coverage.json is reproducible from the live catalogs');
    process.exit(0);
  }
  console.error('i18n coverage.json drifted from the live catalogs — regenerate with:');
  console.error('  node scripts/generate-i18n-coverage.cjs');
  process.exit(1);
}

fs.writeFileSync(OUT, payload);
console.log(`coverage.json written (${snap.total_keys} keys; es ${snap.locales.es.coverage_pct}%, fr ${snap.locales.fr.coverage_pct}%)`);
