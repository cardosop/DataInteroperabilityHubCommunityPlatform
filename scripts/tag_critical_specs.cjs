#!/usr/bin/env node
// Phase 226 PR E1 — `@critical` / `@deprecated` spec-tag enforcement.
//
// Playwright filters with `--grep '@critical'` against the test title. The
// title is whatever string a spec passes to `test.describe()` /
// `test()`. To get fast PR-time feedback (≤ 5 min), the critical-ID specs
// must carry the `@critical` tag in their describe block titles. The
// 6 deprecated phase*.spec.ts files must carry `@deprecated` so the
// nightly full-suite run can opt them out and the PR-time critical-only
// run never touches them.
//
// This script is a deterministic, idempotent tag-injector + checker:
//
//   * READ MODE  (default): scan all spec files and print which specs
//                           are tagged correctly, missing tags, or have
//                           stale tags. Exit 1 if any critical-ID spec
//                           lacks `@critical` or any phase* spec lacks
//                           `@deprecated`.
//   * WRITE MODE (--write): rewrite the first matching `test.describe(`
//                           call's title to include the tag.
//
// We deliberately edit the title (not a sidecar `tags:` annotation): the
// `--grep` matcher is the only filter Playwright applies before sharding,
// and `tags:` was added in 1.42 but is fragile in monorepo configs that
// override the `testInfo.titlePath`. Title-level tags work everywhere.
//
// Critical-ID source: `docs/CRITICAL_UC_JOURNEY_IDS.yaml`. A spec is
// considered "critical" if its file content references at least one of
// the YAML's `critical_use_cases` or `critical_journeys` IDs anywhere in
// the file (header docstring, describe title, or test body).
//
// Plain-Node .cjs to match the existing `assert_*.cjs` scripts; the
// pytest harness exercises both the pure logic and CLI.
//
// Usage:
//   node scripts/tag_critical_specs.cjs
//        [--root=DIR]               (default: frontend/e2e)
//        [--critical-list=PATH]     (default: docs/CRITICAL_UC_JOURNEY_IDS.yaml)
//        [--deprecated=PATH,...]    (comma-list of phase*.spec.ts paths to mark @deprecated)
//        [--write]                  (mutate files; without --write, report only)
//        [--json]                   (machine-readable output)
//
// Exit codes:
//   0  — every critical-ID spec carries `@critical`; every deprecated
//        phase* spec carries `@deprecated`.
//   1  — missing or stale tags found.
//   2  — config error (root missing, malformed YAML, etc.)

'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_ROOT = 'frontend/e2e';
const DEFAULT_CRITICAL_LIST = 'docs/CRITICAL_UC_JOURNEY_IDS.yaml';
// The 6 deprecated phase specs — the legacy "test by phase" structure
// whose coverage has been superseded by per-journey / per-feature specs.
// These files stay on disk through Track D's coverage landing (see 226.E5);
// the @deprecated tag lets the nightly full-suite skip them now and the
// PR-time critical run never see them.
const DEFAULT_DEPRECATED_BASENAMES = [
  'phase2-catalog-journey.spec.ts',
  'phase3-quality-gates.spec.ts',
  'phase4-marketplace-journey.spec.ts',
  'phase6-mesh-virtualization.spec.ts',
  'phase7-social-ai-developer-baas-ml.spec.ts',
  'phase7.5-features-gap-closure.spec.ts',
];

const SKIP_DIR_NAMES = new Set([
  'node_modules',
  'test-results',
  'playwright-report',
  '.auth',
  'dist',
  'build',
  'coverage',
  '__snapshots__',
  'reporters',
  'fixtures',
  'data',
  '_screenshots-for-docs',
  'setup',
]);

// -------------------------------------------------------------- pure logic

/**
 * Extract critical UC and Journey IDs from the YAML file. A minimal YAML
 * subset is enough: the file is hand-maintained and contains only top-level
 * `critical_use_cases:` and `critical_journeys:` lists with `- ID  # comment`
 * entries. Avoiding a yaml dependency keeps this script zero-install.
 *
 * @param {string} yamlSource
 * @returns {{critical_use_cases: string[], critical_journeys: string[]}}
 */
function parseCriticalIds(yamlSource) {
  if (typeof yamlSource !== 'string') {
    return { critical_use_cases: [], critical_journeys: [] };
  }
  const ucs = [];
  const journeys = [];
  let mode = null;
  for (const rawLine of yamlSource.split('\n')) {
    const line = rawLine.replace(/\r$/, '');
    if (/^critical_use_cases\s*:/.test(line)) { mode = 'uc'; continue; }
    if (/^critical_journeys\s*:/.test(line))  { mode = 'j'; continue; }
    // Any non-indented top-level key terminates the current list.
    if (mode && /^[A-Za-z_]/.test(line)) { mode = null; }
    if (!mode) continue;
    const m = line.match(/^\s*-\s*([A-Z][A-Z0-9-]*)\s*(?:#.*)?$/);
    if (!m) continue;
    const id = m[1];
    if (mode === 'uc' && id.startsWith('UC-')) ucs.push(id);
    if (mode === 'j' && id.startsWith('JOURNEY-')) journeys.push(id);
  }
  return {
    critical_use_cases: Array.from(new Set(ucs)).sort(),
    critical_journeys: Array.from(new Set(journeys)).sort(),
  };
}

/**
 * Find which critical IDs are referenced anywhere in the source. A spec
 * "covers" an ID if the ID literal appears in the file (header docstring,
 * describe title, test body, or comment). We deliberately accept comments:
 * the spec author signals the linkage, even if implementation is in helpers.
 *
 * @param {string} source
 * @param {string[]} criticalIds
 * @returns {string[]}
 */
function findCriticalRefs(source, criticalIds) {
  if (typeof source !== 'string' || criticalIds.length === 0) return [];
  const found = [];
  for (const id of criticalIds) {
    // Word-boundary on the surrounding chars so `UC-AUTH-001` doesn't
    // match `UC-AUTH-0011` and `JOURNEY-DPO-001` doesn't match
    // `JOURNEY-DPO-0014`.
    const re = new RegExp(`(?<![A-Z0-9-])${id}(?![A-Z0-9-])`);
    if (re.test(source)) found.push(id);
  }
  return found;
}

/** Detect if a spec already carries the given tag in its describe title. */
function hasTag(source, tag) {
  if (typeof source !== 'string') return false;
  // We accept the tag anywhere in any test.describe / describe title string.
  // Match `(test.)?describe(\s*\(\s*['"`].*<tag>.*['"`]`. Falls through to
  // a fallback substring check if the source is huge but the tag is unique.
  const re = new RegExp(`(?:test\\.)?describe\\s*\\(\\s*['"\`][^'"\`]*${tag.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}[^'"\`]*['"\`]`);
  return re.test(source);
}

/** Returns true if the source contains any `test.describe(...)` call.
 * A spec file with no describe blocks holds no tests — it's either a
 * stub (e.g. the post-split phase7.5 marker) or a typings-only export.
 * Either way the tag check should accept it. */
function hasAnyDescribe(source) {
  if (typeof source !== 'string') return false;
  return /(?:test\.)?describe\s*\(\s*['"`]/.test(source);
}

/**
 * Inject a tag into the FIRST `(test.)?describe(...)` call's title. Returns
 * { changed, source }. If no describe is found, source is unchanged.
 * Idempotent: returns unchanged when the tag is already present.
 *
 * @param {string} source
 * @param {string} tag      e.g. `@critical` (must include leading `@`)
 * @returns {{changed: boolean, source: string}}
 */
function injectTag(source, tag) {
  if (typeof source !== 'string') return { changed: false, source };
  if (hasTag(source, tag)) return { changed: false, source };
  const re = /((?:test\.)?describe\s*\(\s*)(['"`])([^'"`]*)(['"`])/;
  const m = source.match(re);
  if (!m) return { changed: false, source };
  const [whole, prefix, openQ, title, closeQ] = m;
  const newTitle = title.endsWith(' ') ? `${title}${tag}` : `${title} ${tag}`;
  const replacement = `${prefix}${openQ}${newTitle}${closeQ}`;
  return { changed: true, source: source.replace(whole, replacement) };
}

/** Recursive walk that yields .spec.ts paths under root, honoring SKIP_DIR_NAMES. */
function* walkSpecs(root) {
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (e) {
      // dir went missing under us — skip
      continue;
    }
    for (const ent of entries) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (SKIP_DIR_NAMES.has(ent.name) || ent.name.startsWith('.')) continue;
        stack.push(full);
      } else if (ent.isFile() && ent.name.endsWith('.spec.ts')) {
        yield full;
      }
    }
  }
}

// ----------------------------------------------------------------- CLI glue

function parseArgs(argv) {
  const args = {
    root: DEFAULT_ROOT,
    criticalList: DEFAULT_CRITICAL_LIST,
    deprecated: DEFAULT_DEPRECATED_BASENAMES.slice(),
    write: false,
    json: false,
  };
  for (const a of argv.slice(2)) {
    if (a.startsWith('--root=')) args.root = a.slice('--root='.length);
    else if (a.startsWith('--critical-list=')) args.criticalList = a.slice('--critical-list='.length);
    else if (a.startsWith('--deprecated=')) args.deprecated = a.slice('--deprecated='.length).split(',').filter(Boolean);
    else if (a === '--write') args.write = true;
    else if (a === '--json') args.json = true;
    else throw new Error(`unknown arg: ${a}`);
  }
  return args;
}

function run(argv, env, cwd) {
  const args = parseArgs(argv);
  const baseDir = cwd || process.cwd();
  const root = path.isAbsolute(args.root) ? args.root : path.join(baseDir, args.root);
  const listPath = path.isAbsolute(args.criticalList) ? args.criticalList : path.join(baseDir, args.criticalList);

  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    return { exitCode: 2, error: `root not found: ${root}`, result: null };
  }
  if (!fs.existsSync(listPath) || !fs.statSync(listPath).isFile()) {
    return { exitCode: 2, error: `critical-list not found: ${listPath}`, result: null };
  }

  let yamlSource;
  try {
    yamlSource = fs.readFileSync(listPath, 'utf8');
  } catch (e) {
    return { exitCode: 2, error: `failed to read critical-list: ${e.message}`, result: null };
  }

  const ids = parseCriticalIds(yamlSource);
  const criticalIds = [...ids.critical_use_cases, ...ids.critical_journeys];
  if (criticalIds.length === 0) {
    return { exitCode: 2, error: `no critical IDs parsed from ${listPath}`, result: null };
  }

  const deprecatedBasenames = new Set(args.deprecated);

  const criticalReport = [];
  const deprecatedReport = [];

  for (const file of walkSpecs(root)) {
    let source;
    try { source = fs.readFileSync(file, 'utf8'); } catch (_) { continue; }
    const basename = path.basename(file);
    const refs = findCriticalRefs(source, criticalIds);
    const isDeprecated = deprecatedBasenames.has(basename);
    // A deprecated spec is never reported as @critical even if it references
    // a critical ID — its coverage is being moved to per-journey specs and
    // the PR-time `--grep @critical` smoke run must not pull it in.
    const isCritical = refs.length > 0 && !isDeprecated;
    // Stub files (no describe blocks → no tests) cannot be tagged and
    // do not contribute coverage either way. Skip them entirely.
    if (!hasAnyDescribe(source)) continue;
    if (isCritical) {
      const tagged = hasTag(source, '@critical');
      let didWrite = false;
      if (args.write && !tagged) {
        const inj = injectTag(source, '@critical');
        if (inj.changed) {
          fs.writeFileSync(file, inj.source);
          didWrite = true;
        }
      }
      criticalReport.push({
        file: path.relative(baseDir, file),
        ids: refs,
        tagged: tagged || didWrite,
        wrote: didWrite,
      });
    }
    if (isDeprecated) {
      const tagged = hasTag(source, '@deprecated');
      let didWrite = false;
      if (args.write && !tagged) {
        const inj = injectTag(source, '@deprecated');
        if (inj.changed) {
          fs.writeFileSync(file, inj.source);
          didWrite = true;
        }
      }
      deprecatedReport.push({
        file: path.relative(baseDir, file),
        tagged: tagged || didWrite,
        wrote: didWrite,
      });
    }
  }

  const missingCritical = criticalReport.filter((r) => !r.tagged);
  const missingDeprecated = deprecatedReport.filter((r) => !r.tagged);

  const exitCode = (missingCritical.length === 0 && missingDeprecated.length === 0) ? 0 : 1;
  return {
    exitCode,
    error: null,
    result: {
      root,
      critical_id_count: criticalIds.length,
      critical_specs_count: criticalReport.length,
      critical_specs_tagged: criticalReport.length - missingCritical.length,
      deprecated_specs_count: deprecatedReport.length,
      deprecated_specs_tagged: deprecatedReport.length - missingDeprecated.length,
      missing_critical: missingCritical.map((r) => ({ file: r.file, ids: r.ids })),
      missing_deprecated: missingDeprecated.map((r) => ({ file: r.file })),
      wrote: args.write,
    },
  };
}

if (require.main === module) {
  let outcome;
  try {
    outcome = run(process.argv, process.env, process.cwd());
  } catch (e) {
    process.stderr.write(`tag_critical_specs: ${e.message}\n`);
    process.exit(2);
  }
  if (outcome.error) {
    process.stderr.write(`tag_critical_specs: ${outcome.error}\n`);
    process.exit(outcome.exitCode);
  }
  const args = parseArgs(process.argv);
  if (args.json) {
    process.stdout.write(JSON.stringify(outcome.result, null, 2) + '\n');
  } else {
    const r = outcome.result;
    process.stdout.write(
      `tag_critical_specs (${args.write ? 'WRITE' : 'CHECK'}): ` +
      `${r.critical_specs_tagged}/${r.critical_specs_count} critical-ID specs tagged @critical; ` +
      `${r.deprecated_specs_tagged}/${r.deprecated_specs_count} phase* specs tagged @deprecated\n`,
    );
    if (r.missing_critical.length) {
      process.stdout.write('Missing @critical:\n');
      for (const m of r.missing_critical) {
        process.stdout.write(`  - ${m.file}  (${m.ids.join(', ')})\n`);
      }
    }
    if (r.missing_deprecated.length) {
      process.stdout.write('Missing @deprecated:\n');
      for (const m of r.missing_deprecated) {
        process.stdout.write(`  - ${m.file}\n`);
      }
    }
  }
  process.exit(outcome.exitCode);
}

module.exports = {
  parseCriticalIds,
  findCriticalRefs,
  hasTag,
  hasAnyDescribe,
  injectTag,
  parseArgs,
  run,
};
