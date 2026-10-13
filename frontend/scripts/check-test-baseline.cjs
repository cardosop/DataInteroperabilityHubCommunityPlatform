#!/usr/bin/env node
/**
 * Phase U / U.5 — frontend failure-baseline ratchet.
 *
 * Converts the prose baseline ("148 failed / 1703 passed") into a machine
 * ratchet: `frontend/test-results/baseline.json` records the per-file
 * failure/pass counts (quarantined tests excluded), and this checker
 * fails ONLY on NET-NEW failures in a Playwright JSON report — the
 * repo's @quarantine tag policy (docs/test-infrastructure/
 * flaky-test-quarantine-policy.md) keeps flakes from false-redding the
 * gate, and every fixed failure shrinks the recorded floor.
 *
 * Usage:
 *   node scripts/check-test-baseline.js \
 *     --report test-results/results.json \
 *     --baseline test-results/baseline.json
 *   node scripts/check-test-baseline.js --report ... --baseline ... --update
 *
 * Exit codes: 0 clean, 1 net-new failure, 2 usage error.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_REPORT = path.resolve(
  __dirname, '..', 'test-results', 'results.json',
);
const DEFAULT_BASELINE = path.resolve(
  __dirname, '..', 'test-results', 'baseline.json',
);

function parseArgs(argv) {
  const args = { report: DEFAULT_REPORT, baseline: DEFAULT_BASELINE, update: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--report' && argv[i + 1]) {
      args.report = path.resolve(argv[++i]);
    } else if (argv[i] === '--baseline' && argv[i + 1]) {
      args.baseline = path.resolve(argv[++i]);
    } else if (argv[i] === '--update') {
      args.update = true;
    }
  }
  return args;
}

function isQuarantined(test) {
  return Array.isArray(test.tags) && test.tags.some((t) => String(t).includes('@quarantine'));
}

/** Per-file {failed, passed} counts from a Playwright JSON report.
 *
 * The real report nests tests under describe-blocks: top-level suites
 * carry the SPEC FILE as their title, specs live in nested suites. Walk
 * recursively; the file identity comes from the top-level suite title
 * (the .spec.ts path) or the suite.file field.
 */
function countByFile(report) {
  const counts = {};
  function walk(node, file) {
    if (typeof node !== 'object' || node === null) return;
    if (!file && node.file) file = node.file;
    if (!file && typeof node.title === 'string' && node.title.endsWith('.spec.ts')) {
      file = node.title;
    }
    for (const spec of node.specs || []) {
      const f = file
        || (typeof spec.title === 'string' && spec.title.endsWith('.spec.ts') ? spec.title : null)
        || spec.file
        || 'unknown.spec.ts';
      const entry = counts[f] || (counts[f] = { failed: 0, passed: 0 });
      for (const test of spec.tests || []) {
        if (isQuarantined(test)) continue;
        const status = test.status || (test.results || [{}])[0].status;
        if (status === 'failed' || status === 'timedOut') entry.failed += 1;
        else if (status === 'passed' || status === 'expected') entry.passed += 1;
      }
    }
    for (const sub of node.suites || []) walk(sub, file);
  }
  for (const suite of report.suites || []) walk(suite, undefined);
  return counts;
}

function writeBaseline(counts, baselinePath) {
  const payload = {
    generated_at: new Date().toISOString(),
    files: counts,
  };
  fs.mkdirSync(path.dirname(baselinePath), { recursive: true });
  fs.writeFileSync(baselinePath, JSON.stringify(payload, null, 2) + '\n', 'utf8');
}

function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!fs.existsSync(args.report)) {
    console.error(`check-test-baseline: report not found at ${args.report}`);
    return 2;
  }
  const report = JSON.parse(fs.readFileSync(args.report, 'utf8'));
  const counts = countByFile(report);

  if (args.update) {
    writeBaseline(counts, args.baseline);
    const totalFailed = Object.values(counts).reduce((n, c) => n + c.failed, 0);
    const totalPassed = Object.values(counts).reduce((n, c) => n + c.passed, 0);
    console.log(`check-test-baseline: baseline written — ${totalFailed} failed / ${totalPassed} passed across ${Object.keys(counts).length} file(s)`);
    return 0;
  }

  if (!fs.existsSync(args.baseline)) {
    console.error(`check-test-baseline: baseline missing at ${args.baseline} — run with --update after a triaged full run`);
    return 2;
  }
  const baseline = JSON.parse(fs.readFileSync(args.baseline, 'utf8'));
  const baseFiles = baseline.files || {};

  const regressions = [];
  for (const [file, current] of Object.entries(counts)) {
    const base = baseFiles[file];
    // A file absent from the baseline with ANY failure is a regression;
    // a file absent with zero failures is an improvement.
    const floor = base ? base.failed : 0;
    if (current.failed > floor) {
      regressions.push(`${file}: ${current.failed} failed > baseline ${floor}`);
    }
  }

  if (regressions.length > 0) {
    console.error('check-test-baseline: NET-NEW failures over the committed baseline:');
    for (const r of regressions) console.error(`  ${r}`);
    console.error('Quarantined (@quarantine) tests are excluded — re-triage or fix at root; run --update ONLY after an audited run.');
    return 1;
  }

  const totalFailed = Object.values(counts).reduce((n, c) => n + c.failed, 0);
  const totalPassed = Object.values(counts).reduce((n, c) => n + c.passed, 0);
  console.log(`check-test-baseline: clean — ${totalFailed} failed / ${totalPassed} passed (baseline floor respected)`);
  return 0;
}

process.exit(main());
