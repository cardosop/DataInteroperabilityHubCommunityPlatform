#!/usr/bin/env node
/**
 * Phase 226.F1 — Fragile-selector counter for the e2e suite.
 *
 * Scans Playwright `.spec.ts` files for selectors flagged as "fragile":
 *
 *   - `.class-name` style locators (CSS class selectors used as the
 *     primary lookup) — break when the design system renames a class.
 *   - `button:has-text("…")` / `:text("…")` — break when a label is
 *     localised, re-worded, or the button gets an icon-only variant.
 *   - `getByText(...)` / `getByRole(..., { name })` lookups that aren't
 *     wrapped by a `data-testid` (i18n-fragile).
 *
 * For each spec we report:
 *   - testidLookups: count of `getByTestId(...)` and
 *     `[data-testid="…"]` references
 *   - classLookups: count of `.class-name` selector references
 *   - hasTextLookups: count of `:has-text(` / `:text(` occurrences
 *   - byTextLookups: count of `getByText(` calls
 *   - fragileTotal: classLookups + hasTextLookups + byTextLookups
 *   - fragileRatio: fragileTotal / (fragileTotal + testidLookups)
 *
 * Usage:
 *   node scripts/count_fragile_selectors.cjs                         # all specs
 *   node scripts/count_fragile_selectors.cjs --critical              # only specs in critical-list
 *   node scripts/count_fragile_selectors.cjs --json                  # JSON output for CI gate
 *   node scripts/count_fragile_selectors.cjs --top 10                # top-N most fragile
 *   node scripts/count_fragile_selectors.cjs frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts
 *
 * The pure logic (regex matching + per-file aggregation) is exported
 * so `scripts/tests/test_count_fragile_selectors.cjs` can unit-test
 * every branch without touching the filesystem.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');

/**
 * Regex patterns. Kept as module-level so unit tests can re-import
 * and assert behaviour against them.
 */
const PATTERNS = {
  // `getByTestId('foo')` or `[data-testid="foo"]` (or single quotes,
  // backticks, or :has-text-style modifiers). Captures the testid name
  // for completeness; the count is what we use.
  testid: /(?:getByTestId\s*\(|data-testid\s*=)/g,
  // CSS class lookup as a primary locator: `'.app-header'`,
  // `"\.error-display"`, `\`.app-sidebar\``, etc. Excludes contexts
  // where `.foo` is a method call on a Locator (e.g. `.first()`,
  // `.click()`) by requiring quote-then-dot pattern.
  classLookup: /["'`](?:[^"'`,\s]+,\s*)*\.[a-zA-Z][\w-]*(?:\s*,\s*\.[a-zA-Z][\w-]*)*["'`]/g,
  hasText: /:(?:has-text|text)\s*\(/g,
  byText: /getByText\s*\(/g,
  byRoleWithName: /getByRole\s*\([^)]*\bname\s*:\s*["'`]/g,
};

/** Per-file counts. Pure; no I/O. */
function countSelectors(content) {
  const counts = {
    testidLookups: (content.match(PATTERNS.testid) ?? []).length,
    classLookups: (content.match(PATTERNS.classLookup) ?? []).length,
    hasTextLookups: (content.match(PATTERNS.hasText) ?? []).length,
    byTextLookups: (content.match(PATTERNS.byText) ?? []).length,
    byRoleWithNameLookups: (content.match(PATTERNS.byRoleWithName) ?? []).length,
  };
  counts.fragileTotal =
    counts.classLookups +
    counts.hasTextLookups +
    counts.byTextLookups +
    counts.byRoleWithNameLookups;
  counts.totalLookups = counts.fragileTotal + counts.testidLookups;
  counts.fragileRatio =
    counts.totalLookups === 0 ? 0 : counts.fragileTotal / counts.totalLookups;
  return counts;
}

/**
 * Collect candidate spec files. When called with no args, scans
 * `frontend/e2e/**\/*.spec.ts`. With `--critical`, scans only specs
 * matching JOURNEY-* in `frontend/e2e/journeys/**`. With explicit
 * paths, uses those.
 */
function collectSpecPaths(opts) {
  if (opts.explicitPaths.length > 0) {
    return opts.explicitPaths.map((p) => path.resolve(p));
  }
  const baseDir = path.resolve(REPO_ROOT, 'frontend/e2e');
  const out = [];
  const walk = (dir) => {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        // Skip generated/output dirs.
        if (entry.name === 'node_modules' || entry.name === '__snapshots__') continue;
        walk(full);
        continue;
      }
      if (!entry.name.endsWith('.spec.ts')) continue;
      if (opts.critical && !/JOURNEY-/.test(entry.name)) continue;
      out.push(full);
    }
  };
  walk(baseDir);
  return out.sort();
}

function relativise(p) {
  return path.relative(REPO_ROOT, p);
}

function aggregate(perFile) {
  const totals = {
    files: perFile.length,
    testidLookups: 0,
    classLookups: 0,
    hasTextLookups: 0,
    byTextLookups: 0,
    byRoleWithNameLookups: 0,
    fragileTotal: 0,
    totalLookups: 0,
  };
  for (const f of perFile) {
    totals.testidLookups += f.testidLookups;
    totals.classLookups += f.classLookups;
    totals.hasTextLookups += f.hasTextLookups;
    totals.byTextLookups += f.byTextLookups;
    totals.byRoleWithNameLookups += f.byRoleWithNameLookups;
    totals.fragileTotal += f.fragileTotal;
    totals.totalLookups += f.totalLookups;
  }
  totals.fragileRatio =
    totals.totalLookups === 0 ? 0 : totals.fragileTotal / totals.totalLookups;
  return totals;
}

function parseArgs(argv) {
  const opts = {
    json: false,
    critical: false,
    top: null,
    explicitPaths: [],
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--json') opts.json = true;
    else if (a === '--critical') opts.critical = true;
    else if (a === '--top') {
      const n = Number(argv[++i]);
      if (!Number.isFinite(n) || n <= 0) {
        throw new Error(`--top expects a positive integer, got: ${argv[i]}`);
      }
      opts.top = n;
    } else if (a === '--help' || a === '-h') {
      console.log(
        'usage: node scripts/count_fragile_selectors.cjs [--critical] [--json] [--top N] [paths...]',
      );
      process.exit(0);
    } else if (a.startsWith('--')) {
      throw new Error(`Unknown option: ${a}`);
    } else {
      opts.explicitPaths.push(a);
    }
  }
  return opts;
}

function main(argv) {
  const opts = parseArgs(argv.slice(2));
  const paths = collectSpecPaths(opts);
  const perFile = paths.map((p) => {
    let content = '';
    try {
      content = fs.readFileSync(p, 'utf8');
    } catch (err) {
      console.error(`[count_fragile_selectors] cannot read ${p}: ${err.message}`);
      return null;
    }
    const counts = countSelectors(content);
    return { file: relativise(p), ...counts };
  }).filter(Boolean);

  const totals = aggregate(perFile);

  let ranked = perFile
    .filter((f) => f.fragileTotal > 0)
    .sort((a, b) => b.fragileTotal - a.fragileTotal);
  if (opts.top !== null) ranked = ranked.slice(0, opts.top);

  const out = { totals, ranked, scanned: perFile.length };
  if (opts.json) {
    process.stdout.write(JSON.stringify(out, null, 2) + '\n');
    return 0;
  }

  // Human-readable Markdown-ish table.
  console.log(`# Fragile-selector report (${perFile.length} spec files scanned)\n`);
  console.log(`Total fragile selector usages: **${totals.fragileTotal}**`);
  console.log(`Total data-testid lookups:     **${totals.testidLookups}**`);
  console.log(`Fragile / total ratio:         **${(totals.fragileRatio * 100).toFixed(1)}%**`);
  console.log('');
  if (ranked.length > 0) {
    const topLabel = opts.top === null ? 'All' : `Top ${opts.top}`;
    console.log(`## ${topLabel} specs by fragile-selector count\n`);
    console.log('| File | fragile | testid | class | has-text | byText | byRole(name) | ratio |');
    console.log('|------|--------:|-------:|------:|---------:|-------:|-------------:|------:|');
    for (const f of ranked) {
      const ratio =
        f.totalLookups === 0 ? '—' : `${(f.fragileRatio * 100).toFixed(0)}%`;
      console.log(
        `| ${f.file} | ${f.fragileTotal} | ${f.testidLookups} | ${f.classLookups} | ${f.hasTextLookups} | ${f.byTextLookups} | ${f.byRoleWithNameLookups} | ${ratio} |`,
      );
    }
  }
  return 0;
}

module.exports = {
  PATTERNS,
  countSelectors,
  aggregate,
  collectSpecPaths,
  parseArgs,
};

if (require.main === module) {
  try {
    process.exit(main(process.argv));
  } catch (err) {
    console.error(`[count_fragile_selectors] ${err && err.message ? err.message : err}`);
    process.exit(1);
  }
}
