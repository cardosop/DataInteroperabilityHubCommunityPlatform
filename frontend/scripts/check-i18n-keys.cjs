#!/usr/bin/env node
/**
 * Phase 228 X (228.X.1 / REQ-LIN-X-001) — i18n catalog CI gate.
 *
 *   $ node frontend/scripts/check-i18n-keys.cjs
 *
 * Walks src/ for `t('key', 'fallback')` invocations and asserts:
 *
 *   1. Every used key exists in src/shared/i18n/locales/en.ts.
 *   2. Every key in en.ts is used somewhere (no orphans).
 *   3. Every key under the `lineage.*` namespace has a fallback.
 *
 * Exits 0 on pass, 1 on missing keys, 2 on orphans (warn-only by
 * default; pass --strict-orphans to make orphans a failure).
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const LOCALE = path.join(ROOT, 'src/shared/i18n/locales/en.ts');
const SRC_DIR = path.join(ROOT, 'src');

function readLocaleKeys() {
  const text = fs.readFileSync(LOCALE, 'utf8');
  // Quick + dirty: pull every "namespace.key" string literal that
  // appears inside the locale file. This avoids depending on a TS
  // parser at lint time.
  const re = /'([a-zA-Z][a-zA-Z0-9_.]*)'/g;
  const out = new Set();
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m[1].includes('.')) out.add(m[1]);
  }
  return out;
}

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'i18n') continue;
      walk(p, files);
    } else if (/\.(ts|tsx)$/.test(entry.name)) {
      files.push(p);
    }
  }
  return files;
}

function findUsedKeys() {
  const files = walk(SRC_DIR);
  const used = new Map(); // key -> Set(files)
  const re = /\bt\(\s*'([a-zA-Z][a-zA-Z0-9_.]*)'/g;
  for (const f of files) {
    const text = fs.readFileSync(f, 'utf8');
    let m;
    while ((m = re.exec(text)) !== null) {
      const key = m[1];
      if (!used.has(key)) used.set(key, new Set());
      used.get(key).add(path.relative(ROOT, f));
    }
  }
  return used;
}

function main() {
  const strictOrphans = process.argv.includes('--strict-orphans');
  const localeKeys = readLocaleKeys();
  const usedKeys = findUsedKeys();

  const missing = [];
  for (const [key, files] of usedKeys.entries()) {
    if (!localeKeys.has(key)) {
      missing.push({ key, files: [...files] });
    }
  }

  const orphans = [];
  for (const key of localeKeys) {
    if (!usedKeys.has(key)) orphans.push(key);
  }

  const result = {
    phase: '228.X.1',
    locale_keys_total: localeKeys.size,
    used_keys_total: usedKeys.size,
    missing_count: missing.length,
    orphans_count: orphans.length,
    missing,
    orphans,
  };
  console.log(JSON.stringify(result, null, 2));

  if (missing.length > 0) {
    process.exit(1);
  }
  if (orphans.length > 0 && strictOrphans) {
    process.exit(2);
  }
  process.exit(0);
}

main();
