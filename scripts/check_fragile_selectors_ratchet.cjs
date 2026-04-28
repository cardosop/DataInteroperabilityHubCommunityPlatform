#!/usr/bin/env node
/**
 * Phase 226.F1.b — Fragile-selector ratchet gate.
 *
 * CI gate that prevents PRs from regressing the fragile-selector
 * baseline. Computes the current count via
 * `count_fragile_selectors.cjs`, compares against
 * `frontend/e2e/.fragile-baseline.json`, and exits non-zero if either:
 *
 *   - `fragileTotal` is greater than `baseline.fragileTotal +
 *     tolerance.fragileTotalAllowDelta` (default 0 — strict ratchet).
 *
 *   - `fragileRatio` increased by more than
 *     `tolerance.fragileRatioAllowDelta` (default 0.005 — half a
 *     percentage point of breathing room for rounding).
 *
 * To intentionally update the baseline (e.g. after a deliberate
 * migration that LOWERS the count, or a one-off acceptable rise that
 * the team has reviewed), pass `--update` and the new totals are
 * written back. The git diff on `frontend/e2e/.fragile-baseline.json`
 * is the durable record of the change.
 *
 * Usage:
 *   node scripts/check_fragile_selectors_ratchet.cjs
 *   node scripts/check_fragile_selectors_ratchet.cjs --json
 *   node scripts/check_fragile_selectors_ratchet.cjs --update
 *
 * Pure logic exported for unit testing.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const {
  countSelectors,
  aggregate,
  collectSpecPaths,
} = require('./count_fragile_selectors.cjs');

const REPO_ROOT = path.resolve(__dirname, '..');
const BASELINE_PATH = path.resolve(
  REPO_ROOT,
  'frontend',
  'e2e',
  '.fragile-baseline.json',
);

/**
 * Pure decision: given a baseline + current totals, compute pass/fail
 * + a list of human-readable problem strings. No I/O.
 */
function evaluateRatchet(baseline, current) {
  const tolerance = baseline.tolerance ?? {};
  const fragileTotalAllowDelta = Number(tolerance.fragileTotalAllowDelta ?? 0);
  const fragileRatioAllowDelta = Number(tolerance.fragileRatioAllowDelta ?? 0.005);

  const fragileTotalDelta = current.fragileTotal - baseline.fragileTotal;
  const fragileRatioDelta = current.fragileRatio - baseline.fragileRatio;

  const problems = [];

  if (fragileTotalDelta > fragileTotalAllowDelta) {
    problems.push(
      `fragileTotal regressed: ${baseline.fragileTotal} → ${current.fragileTotal} ` +
        `(+${fragileTotalDelta}; tolerance +${fragileTotalAllowDelta})`,
    );
  }
  if (fragileRatioDelta > fragileRatioAllowDelta) {
    problems.push(
      `fragileRatio regressed: ${(baseline.fragileRatio * 100).toFixed(2)}% → ` +
        `${(current.fragileRatio * 100).toFixed(2)}% ` +
        `(+${(fragileRatioDelta * 100).toFixed(2)} pp; tolerance +${(fragileRatioAllowDelta * 100).toFixed(2)} pp)`,
    );
  }

  return {
    passed: problems.length === 0,
    problems,
    fragileTotalDelta,
    fragileRatioDelta,
    baseline: {
      fragileTotal: baseline.fragileTotal,
      fragileRatio: baseline.fragileRatio,
    },
    current: {
      fragileTotal: current.fragileTotal,
      fragileRatio: current.fragileRatio,
    },
  };
}

function loadBaseline() {
  if (!fs.existsSync(BASELINE_PATH)) {
    throw new Error(
      `Fragile-selector baseline not found at ${path.relative(
        REPO_ROOT,
        BASELINE_PATH,
      )}. Bootstrap with \`node scripts/check_fragile_selectors_ratchet.cjs --update\`.`,
    );
  }
  return JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'));
}

function computeCurrent() {
  const paths = collectSpecPaths({ critical: false, explicitPaths: [] });
  const perFile = paths.map((p) => {
    const content = fs.readFileSync(p, 'utf8');
    return { file: p, ...countSelectors(content) };
  });
  return aggregate(perFile);
}

function writeBaseline(currentTotals, prev) {
  const prevTolerance = prev?.tolerance ?? { fragileTotalAllowDelta: 0, fragileRatioAllowDelta: 0.005 };
  const out = {
    capturedAt: new Date().toISOString().slice(0, 10),
    phase: prev?.phase ?? '226.F1.b',
    note:
      prev?.note ??
      'Fragile-selector baseline. The CI gate fails if fragileTotal exceeds this number, OR if fragileRatio increases by more than the configured tolerance.',
    fragileTotal: currentTotals.fragileTotal,
    testidLookups: currentTotals.testidLookups,
    totalLookups: currentTotals.totalLookups,
    fragileRatio: currentTotals.fragileRatio,
    tolerance: prevTolerance,
  };
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(out, null, 2) + '\n');
  return out;
}

function parseArgs(argv) {
  const opts = { json: false, update: false };
  for (const a of argv) {
    if (a === '--json') opts.json = true;
    else if (a === '--update') opts.update = true;
    else if (a === '--help' || a === '-h') {
      console.log(
        'usage: node scripts/check_fragile_selectors_ratchet.cjs [--json] [--update]',
      );
      process.exit(0);
    } else {
      throw new Error(`Unknown option: ${a}`);
    }
  }
  return opts;
}

function main(argv) {
  const opts = parseArgs(argv.slice(2));
  const current = computeCurrent();

  if (opts.update) {
    const prev = fs.existsSync(BASELINE_PATH)
      ? JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'))
      : null;
    const updated = writeBaseline(current, prev);
    if (opts.json) {
      process.stdout.write(JSON.stringify({ updated: true, baseline: updated }, null, 2) + '\n');
    } else {
      console.log(`Baseline updated:\n  fragileTotal: ${updated.fragileTotal}\n  fragileRatio: ${(updated.fragileRatio * 100).toFixed(2)}%`);
    }
    return 0;
  }

  const baseline = loadBaseline();
  const result = evaluateRatchet(baseline, current);

  if (opts.json) {
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } else if (result.passed) {
    console.log(
      `[fragile-ratchet] PASS ` +
        `fragileTotal=${result.current.fragileTotal} (baseline ${result.baseline.fragileTotal}, delta ${result.fragileTotalDelta >= 0 ? '+' : ''}${result.fragileTotalDelta}) ` +
        `fragileRatio=${(result.current.fragileRatio * 100).toFixed(2)}% (baseline ${(result.baseline.fragileRatio * 100).toFixed(2)}%)`,
    );
  } else {
    console.error('[fragile-ratchet] FAIL');
    for (const p of result.problems) console.error(`  - ${p}`);
    console.error(
      `\nIf this regression is intentional, run \`node scripts/check_fragile_selectors_ratchet.cjs --update\` ` +
        `to bump the baseline and commit the change.`,
    );
  }

  return result.passed ? 0 : 1;
}

module.exports = {
  evaluateRatchet,
  parseArgs,
  computeCurrent,
};

if (require.main === module) {
  try {
    process.exit(main(process.argv));
  } catch (err) {
    console.error(`[check_fragile_selectors_ratchet] ${err && err.message ? err.message : err}`);
    process.exit(1);
  }
}
