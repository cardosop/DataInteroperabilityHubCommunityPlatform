/**
 * Phase U / U.5 — TDD suite for the frontend failure-baseline checker.
 *
 * The mechanism converts "148 failed/1703 passed (recorded in prose)" into
 * a machine ratchet: a committed per-file baseline of failure counts, and
 * a checker that fails ONLY on NET-NEW failures in a Playwright JSON
 * report — quarantined tests (the repo's @quarantine tag policy) never
 * count against the baseline, so flakes cannot false-red the gate.
 *
 * Run: node scripts/tests/test_check_test_baseline.cjs
 */

'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');

const CHECKER = path.resolve(
  __dirname, '..', '..', 'frontend', 'scripts', 'check-test-baseline.cjs',
);

let passed = 0;
let failed = 0;

function eq(label, actual, expected) {
  if (actual === expected) { passed++; return; }
  failed++;
  console.error(`✘ ${label}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
}
function truthy(label, actual) { eq(label, actual, true); }

/** Playwright JSON report builder — mirrors the REAL report shape:
 * top-level suites carry the .spec.ts FILE as their title; tests live in
 * nested specs below. */
function report(files) {
  const suites = Object.entries(files).map(([file, tests]) => ({
    title: file,
    file,
    suites: [{
      title: file,
      specs: [{
        title: 'describe',
        ok: tests.every((t) => t.status === 'passed'),
        tests: tests.map((t) => ({
          status: t.status,
          title: t.title,
          results: [{ status: t.status }],
          tags: t.tags || [],
        })),
      }],
      suites: [],
    }],
    specs: [],
  }));
  return { config: { rootDir: '/repo' }, suites };
}

function run(argv, cwd) {
  const { spawnSync } = require('child_process');
  const result = spawnSync('node', [CHECKER, ...argv], {
    cwd: cwd || __dirname,
    encoding: 'utf8',
  });
  return { code: result.status, out: result.stdout + result.stderr };
}

function tempdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'test-baseline-'));
}

// ── Quarantine awareness ────────────────────────────────────────────────────

{
  const dir = tempdir();
  fs.writeFileSync(path.join(dir, 'baseline.json'), JSON.stringify({
    generated_at: '2026-08-31T00:00:00Z',
    files: { 'a.spec.ts': { failed: 1, passed: 3 } },
  }));
  // One new failure, but it is @quarantine-tagged — must NOT fail the gate.
  fs.writeFileSync(path.join(dir, 'results.json'), JSON.stringify(report({
    'a.spec.ts': [
      { title: 'old failure', status: 'failed' },
      { title: 'quarantined flake', status: 'failed', tags: ['@quarantine'] },
      { title: 'p1', status: 'passed' },
      { title: 'p2', status: 'passed' },
    ],
  })));
  const r = run([
    '--report', path.join(dir, 'results.json'),
    '--baseline', path.join(dir, 'baseline.json'),
  ]);
  eq('quarantined failure does not count against the baseline', r.code, 0);
}

// ── Net-new failure ratchet ─────────────────────────────────────────────────

{
  const dir = tempdir();
  fs.writeFileSync(path.join(dir, 'baseline.json'), JSON.stringify({
    generated_at: '2026-08-31T00:00:00Z',
    files: { 'a.spec.ts': { failed: 1, passed: 3 } },
  }));
  fs.writeFileSync(path.join(dir, 'results.json'), JSON.stringify(report({
    'a.spec.ts': [
      { title: 'old failure', status: 'failed' },
      { title: 'NEW regression', status: 'failed' },
      { title: 'p1', status: 'passed' },
      { title: 'p2', status: 'passed' },
    ],
  })));
  const r = run([
    '--report', path.join(dir, 'results.json'),
    '--baseline', path.join(dir, 'baseline.json'),
  ]);
  eq('net-new failure fails the gate', r.code, 1);
  truthy('failure names the regressed file', r.out.includes('a.spec.ts'));
}

// ── Improvements pass ───────────────────────────────────────────────────────

{
  const dir = tempdir();
  fs.writeFileSync(path.join(dir, 'baseline.json'), JSON.stringify({
    generated_at: '2026-08-31T00:00:00Z',
    files: { 'a.spec.ts': { failed: 2, passed: 2 } },
  }));
  fs.writeFileSync(path.join(dir, 'results.json'), JSON.stringify(report({
    'a.spec.ts': [
      { title: 'old failure', status: 'failed' },
      { title: 'p1', status: 'passed' },
      { title: 'p2', status: 'passed' },
      { title: 'p3', status: 'passed' },
    ],
  })));
  const r = run([
    '--report', path.join(dir, 'results.json'),
    '--baseline', path.join(dir, 'baseline.json'),
  ]);
  eq('fewer failures than baseline pass', r.code, 0);
}

// ── New file with no baseline entry ─────────────────────────────────────────

{
  const dir = tempdir();
  fs.writeFileSync(path.join(dir, 'baseline.json'), JSON.stringify({
    generated_at: '2026-08-31T00:00:00Z',
    files: {},
  }));
  fs.writeFileSync(path.join(dir, 'results.json'), JSON.stringify(report({
    'new.spec.ts': [{ title: 'failing new spec', status: 'failed' }],
  })));
  const r = run([
    '--report', path.join(dir, 'results.json'),
    '--baseline', path.join(dir, 'baseline.json'),
  ]);
  eq('a failing file absent from the baseline fails the gate', r.code, 1);
}

// ── Baseline generation ─────────────────────────────────────────────────────

{
  const dir = tempdir();
  fs.writeFileSync(path.join(dir, 'results.json'), JSON.stringify(report({
    'a.spec.ts': [
      { title: 'x', status: 'failed' },
      { title: 'y', status: 'failed', tags: ['@quarantine'] },
      { title: 'z', status: 'passed' },
    ],
  })));
  const r = run([
    '--report', path.join(dir, 'results.json'),
    '--baseline', path.join(dir, 'baseline.json'),
    '--update',
  ]);
  eq('--update writes the baseline', r.code, 0);
  const written = JSON.parse(
    fs.readFileSync(path.join(dir, 'baseline.json'), 'utf8'),
  );
  // Quarantined failures are excluded from the recorded floor.
  eq('baseline excludes quarantined failures', written.files['a.spec.ts'].failed, 1);
  eq('baseline records passes', written.files['a.spec.ts'].passed, 1);
}

if (failed > 0) {
  console.error(`\n${failed} test(s) failed, ${passed} passed`);
  process.exit(1);
}
console.log(`check-test-baseline contract pinned: ${passed}/${passed} passed`);
