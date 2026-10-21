#!/usr/bin/env node
// Phase 226 PR C1 — `page.waitForTimeout` budget CI gate.
//
// Hard-coded sleeps (`page.waitForTimeout(N)`) are the dominant source of
// Playwright flake in this repo: the wait is either too short (race lost,
// test fails on the runner under load) or too long (CI wall-time creeps up
// silently). Track 226.C1 retired the worst offenders; this gate prevents
// regression.
//
// CI runs: `node scripts/assert_waitfortimeout_budget.cjs`. The current
// budget lives at `scripts/waitfortimeout_budget.json`. To raise it (you
// removed waits) — drop the number. To lower it (you added a wait) — first
// justify why an event-based wait won't work, then bump the budget in the
// same PR.
//
// Plain-Node .cjs to match the existing `scripts/assert_mutation_coverage.cjs`
// pattern: no ts-node dependency, exports usable from pytest harness.
//
// Usage:
//   node scripts/assert_waitfortimeout_budget.cjs
//        [--budget=N]               (overrides budget file)
//        [--budget-file=PATH]       (default: scripts/waitfortimeout_budget.json)
//        [--root=DIR]               (default: frontend/e2e)
//        [--exclude=GLOB,...]       (skip listed file basenames; default: empty)
//        [--json]                   (machine-readable output)
//        [--update-budget]          (writes the current count back to the budget file)
//
// Exit codes:
//   0  — count <= budget
//   1  — count > budget
//   2  — config error (root missing, malformed budget, etc.)

'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_BUDGET_FILE = 'scripts/waitfortimeout_budget.json';
const DEFAULT_ROOT = 'frontend/e2e';

// Directories that should never be walked: build artefacts, vendor code,
// reporter outputs, screenshots — none of which represent test logic.
const SKIP_DIR_NAMES = new Set([
  'node_modules',
  'test-results',
  'playwright-report',
  '.auth',
  'dist',
  'build',
  '.next',
  'coverage',
  '__snapshots__',
]);

// File extensions we scan. helpers.ts is the largest single offender and is
// not a `.spec.ts`; we therefore include `.ts` and `.tsx` and let the
// directory walk skip non-test artefact dirs above.
const SCAN_EXTENSIONS = new Set(['.ts', '.tsx', '.mts', '.cts']);

// -------------------------------------------------------------- pure logic

/**
 * Match `<expr>.waitForTimeout(...)` in source — captures both the canonical
 * `page.waitForTimeout(N)` and chained-locator / variable forms (`p.waitForTimeout`,
 * `otherPage.waitForTimeout`). False positives on identifiers literally named
 * `waitForTimeout` outside the Playwright context are unlikely in this repo
 * and would still represent a hard sleep worth flagging.
 *
 * Lines that begin with a line-comment marker (`//`) or block-comment
 * continuation (`*` / `/*`) are skipped: JSDoc and inline comments often
 * *describe* `waitForTimeout` calls (e.g. "// removed waitForTimeout(...)")
 * and shouldn't count against the budget.
 *
 * @param {string} source
 * @returns {number}
 */
function countWaitForTimeout(source) {
  if (typeof source !== 'string' || source.length === 0) return 0;
  const callRe = /\.\s*waitForTimeout\s*\(/g;
  const commentLineRe = /^\s*(\/\/|\*|\/\*)/;
  let n = 0;
  for (const line of source.split('\n')) {
    if (commentLineRe.test(line)) continue;
    const matches = line.match(callRe);
    if (matches) n += matches.length;
  }
  return n;
}

// Cheap glob-ish matcher: caller passes a plain basename (e.g.
// `phase8-hardening.spec.ts`) or a `*` suffix wildcard. A full glob library
// is overkill — the gate's job is "skip a known offender during ratchet"
// which is always a basename match.
function basenameMatchesAny(basename, patterns) {
  for (const p of patterns) {
    if (!p) continue;
    if (p === basename) return true;
    if (p.endsWith('*') && basename.startsWith(p.slice(0, -1))) return true;
  }
  return false;
}

// ------------------------------------------------------------ CLI wrapper

function parseArgs(argv) {
  const args = {
    budget: null, // resolved later from file or --budget=N
    budgetFile: DEFAULT_BUDGET_FILE,
    root: DEFAULT_ROOT,
    exclude: [],
    json: false,
    updateBudget: false,
  };
  for (const a of argv) {
    if (a.startsWith('--budget=')) {
      const v = a.slice(9);
      const n = Number.parseInt(v, 10);
      if (!Number.isFinite(n) || String(n) !== v) {
        return { error: `invalid --budget value: ${v}` };
      }
      args.budget = n;
    } else if (a.startsWith('--budget-file=')) {
      args.budgetFile = a.slice(14);
    } else if (a.startsWith('--root=')) {
      args.root = a.slice(7);
    } else if (a.startsWith('--exclude=')) {
      const list = a.slice(10).split(',').map((s) => s.trim()).filter(Boolean);
      args.exclude.push(...list);
    } else if (a === '--json') {
      args.json = true;
    } else if (a === '--update-budget') {
      args.updateBudget = true;
    }
  }
  return args;
}

function walkSourceFiles(dir, excludeBasenames, out) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch (err) {
    // Surface to caller — main() turns it into exit code 2.
    throw err;
  }
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (SKIP_DIR_NAMES.has(entry.name)) continue;
      if (entry.name.startsWith('.')) continue; // dotdirs (.auth, .git, .vite)
      walkSourceFiles(path.join(dir, entry.name), excludeBasenames, out);
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name);
      if (!SCAN_EXTENSIONS.has(ext)) continue;
      if (basenameMatchesAny(entry.name, excludeBasenames)) continue;
      out.push(path.join(dir, entry.name));
    }
  }
  return out;
}

function readBudgetFile(file) {
  if (!fs.existsSync(file)) return null;
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch (err) {
    throw new Error(`failed to read budget file ${file}: ${err.message}`);
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`malformed budget file ${file}: ${err.message}`);
  }
  if (!parsed || typeof parsed.budget !== 'number' || !Number.isInteger(parsed.budget)) {
    throw new Error(`budget file ${file} missing integer 'budget' field`);
  }
  if (parsed.budget < 0) {
    throw new Error(`budget file ${file} has negative budget`);
  }
  return parsed.budget;
}

function writeBudgetFile(file, count) {
  const payload = {
    budget: count,
    note:
      'Phase 226 C1 ratchet — only ever lower this number. ' +
      'Adding a waitForTimeout requires raising the budget in the same PR with justification.',
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(file, `${JSON.stringify(payload, null, 2)}\n`);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.error) {
    process.stderr.write(`assert_waitfortimeout_budget: ${args.error}\n`);
    return 2;
  }

  if (!fs.existsSync(args.root)) {
    process.stderr.write(
      `assert_waitfortimeout_budget: root not found: ${args.root}\n`,
    );
    return 2;
  }

  let budget;
  if (args.budget !== null) {
    budget = args.budget;
  } else {
    try {
      const fromFile = readBudgetFile(args.budgetFile);
      if (fromFile === null) {
        process.stderr.write(
          `assert_waitfortimeout_budget: budget file not found: ${args.budgetFile} (pass --budget=N or create the file)\n`,
        );
        return 2;
      }
      budget = fromFile;
    } catch (err) {
      process.stderr.write(`assert_waitfortimeout_budget: ${err.message}\n`);
      return 2;
    }
  }

  let files;
  try {
    files = walkSourceFiles(args.root, args.exclude, []);
  } catch (err) {
    process.stderr.write(
      `assert_waitfortimeout_budget: walk failed: ${err.message}\n`,
    );
    return 2;
  }

  let total = 0;
  const perFile = [];
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    const n = countWaitForTimeout(src);
    if (n > 0) perFile.push({ file: f, count: n });
    total += n;
  }

  perFile.sort((a, b) => b.count - a.count);

  const overBudget = total > budget;

  if (args.json) {
    process.stdout.write(
      `${JSON.stringify(
        {
          count: total,
          budget,
          overBudget,
          filesScanned: files.length,
          topOffenders: perFile.slice(0, 25),
        },
        null,
        2,
      )}\n`,
    );
  } else {
    process.stdout.write(
      `assert_waitfortimeout_budget: scanned ${files.length} source files in ${args.root}\n`,
    );
    process.stdout.write(`  total waitForTimeout calls: ${total}\n`);
    process.stdout.write(`  budget: ${budget}\n`);
    if (perFile.length > 0) {
      process.stdout.write('  top offenders:\n');
      for (const e of perFile.slice(0, 20)) {
        process.stdout.write(`    ${e.count.toString().padStart(4)}  ${e.file}\n`);
      }
    }
    if (overBudget) {
      process.stdout.write(
        `\n  ✗ over budget by ${total - budget}. Either replace the new waitForTimeout(s)\n` +
          '    with event-based waits (waitForResponse / locator.waitFor / waitForFunction),\n' +
          '    or — if a hard sleep is genuinely required — bump the budget in this PR\n' +
          `    by editing ${args.budgetFile} and explain why in the commit message.\n`,
      );
    } else if (total < budget) {
      process.stdout.write(
        `\n  ✓ under budget by ${budget - total}. Run with --update-budget to ratchet down.\n`,
      );
    } else {
      process.stdout.write('\n  ✓ at budget.\n');
    }
  }

  if (args.updateBudget) {
    try {
      writeBudgetFile(args.budgetFile, total);
      process.stderr.write(
        `assert_waitfortimeout_budget: budget file updated to ${total}\n`,
      );
    } catch (err) {
      process.stderr.write(
        `assert_waitfortimeout_budget: failed to write budget: ${err.message}\n`,
      );
      return 2;
    }
  }

  return overBudget ? 1 : 0;
}

// Exports used by the pytest harness in scripts/tests/.
module.exports = {
  countWaitForTimeout,
  basenameMatchesAny,
  walkSourceFiles,
  readBudgetFile,
};

if (require.main === module) {
  process.exit(main());
}
