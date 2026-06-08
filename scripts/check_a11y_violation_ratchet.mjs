#!/usr/bin/env node
/**
 * Phase 278.U.4 — a11y violation ratchet script.
 *
 * Reads the per-page violation counts emitted by `runAxeAudit()` when
 * `E2E_A11Y_RATCHET_OUTPUT` is set (see `frontend/e2e/fixtures/axeAudit.ts`)
 * and compares them against the committed baseline
 * (`frontend/e2e/a11y/violationCounts.json`).
 *
 * CI contract:
 *   - Exits 0 when no page's moderate+minor violations INCREASED relative
 *     to baseline.
 *   - Exits 1 when any page's count increased (ratchet violation).
 *   - First-run mode (baseline `_first_run: true` OR all counts `-1`):
 *     overwrites the baseline with observed counts and exits 0.
 *
 * Intentional scope: only moderate + minor.  Critical + serious violations
 * fail the test directly via `expectNoSeriousViolations()` in the spec and
 * are not tracked by this script.
 *
 * Usage:
 *   E2E_A11Y_RATCHET_OUTPUT=/tmp/a11y-ratchet.jsonl npx playwright test --project=chromium e2e/a11y/
 *   node scripts/check_a11y_violation_ratchet.mjs /tmp/a11y-ratchet.jsonl
 */

import { readFile, writeFile } from 'node:fs/promises';
import { exit } from 'node:process';

const BASELINE_PATH = new URL(
  '../frontend/e2e/a11y/violationCounts.json',
  import.meta.url,
).pathname;

function usage() {
  console.error('Usage: node scripts/check_a11y_violation_ratchet.mjs <ratchet-output.jsonl>');
  console.error('');
  console.error('  ratchet-output.jsonl — file produced by axeAudit.ts when');
  console.error('  E2E_A11Y_RATCHET_OUTPUT is set. One JSON line per audit.');
  exit(2);
}

/**
 * Parse the JSONL output file produced by runAxeAudit().
 * Returns a Map of label → { moderate, minor, total }.
 */
async function parseRatchetOutput(filePath) {
  const raw = await readFile(filePath, 'utf-8');
  const counts = new Map();
  for (const line of raw.trim().split('\n')) {
    if (!line.trim()) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      console.warn(`[a11y-ratchet] skipping malformed line: ${line.slice(0, 80)}`);
      continue;
    }
    const { label, moderate, minor, total } = record;
    if (!label) continue;
    // If the same label appears multiple times (e.g. a page audited in
    // multiple states), take the max per category so a flaky-passing
    // audit doesn't mask a real violation on the other state.
    const prev = counts.get(label);
    counts.set(label, {
      moderate: Math.max(prev?.moderate ?? 0, moderate ?? 0),
      minor: Math.max(prev?.minor ?? 0, minor ?? 0),
      total: Math.max(prev?.total ?? 0, total ?? 0),
    });
  }
  return counts;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length !== 1 || args[0] === '--help' || args[0] === '-h') {
    usage();
  }
  const ratchetOutputPath = args[0];

  let observed;
  try {
    observed = await parseRatchetOutput(ratchetOutputPath);
  } catch (err) {
    console.error(`[a11y-ratchet] cannot read ratchet output: ${err.message}`);
    console.error('[a11y-ratchet] ensure E2E_A11Y_RATCHET_OUTPUT was set during the Playwright run.');
    exit(2);
  }

  if (observed.size === 0) {
    console.warn('[a11y-ratchet] no audit records found in ratchet output — nothing to compare.');
    console.warn('[a11y-ratchet] this may indicate the a11y tests did not run or no audits executed.');
    exit(0);
  }

  let baseline;
  try {
    const raw = await readFile(BASELINE_PATH, 'utf-8');
    baseline = JSON.parse(raw);
  } catch {
    console.error(`[a11y-ratchet] cannot read baseline: ${BASELINE_PATH}`);
    exit(2);
  }

  const pages = baseline.pages ?? {};
  const isFirstRun = baseline._first_run === true;

  // ── First-run: auto-populate the baseline ─────────────────────────
  if (isFirstRun) {
    const updated = {};
    for (const [label, counts] of observed) {
      updated[label] = { moderate: counts.moderate, minor: counts.minor };
    }
    // Preserve any baseline entries NOT observed in this run.
    for (const [label, entry] of Object.entries(pages)) {
      if (!updated[label] && entry.moderate === -1 && entry.minor === -1) {
        updated[label] = { moderate: -1, minor: -1 };
      }
    }
    // Add newly-observed pages not yet in baseline.
    for (const [label, counts] of observed) {
      if (!updated[label]) {
        updated[label] = { moderate: counts.moderate, minor: counts.minor };
      }
    }
    baseline._first_run = false;
    baseline._updated = new Date().toISOString().slice(0, 10);
    baseline.pages = updated;
    await writeFile(BASELINE_PATH, JSON.stringify(baseline, null, 2) + '\n', 'utf-8');
    console.log(
      `[a11y-ratchet] FIRST RUN — baseline populated with ${Object.keys(updated).length} page(s).`,
    );
    console.log(`[a11y-ratchet] commit the updated ${BASELINE_PATH} to activate the ratchet.`);
    exit(0);
  }

  // ── Ratchet check ─────────────────────────────────────────────────
  const violations = [];
  for (const [label, observedCounts] of observed) {
    const baselineEntry = pages[label];
    if (!baselineEntry) {
      // New page not in baseline — auto-add at current counts (first
      // observation for a new page is the baseline).
      console.warn(`[a11y-ratchet] new page "${label}" — adding to baseline at current counts.`);
      pages[label] = {
        moderate: observedCounts.moderate,
        minor: observedCounts.minor,
      };
      baseline._updated = new Date().toISOString().slice(0, 10);
      continue;
    }
    if (baselineEntry.moderate === -1 && baselineEntry.minor === -1) {
      // Placeholder entry — populate it.
      pages[label] = {
        moderate: observedCounts.moderate,
        minor: observedCounts.minor,
      };
      baseline._updated = new Date().toISOString().slice(0, 10);
      continue;
    }
    const modDelta = observedCounts.moderate - (baselineEntry.moderate ?? 0);
    const minDelta = observedCounts.minor - (baselineEntry.minor ?? 0);
    if (modDelta > 0 || minDelta > 0) {
      violations.push({
        label,
        baseline: { moderate: baselineEntry.moderate, minor: baselineEntry.minor },
        observed: { moderate: observedCounts.moderate, minor: observedCounts.minor },
        delta: { moderate: modDelta, minor: minDelta },
      });
    }
  }

  // Write back any auto-added entries.
  if (baseline._updated === new Date().toISOString().slice(0, 10)) {
    await writeFile(BASELINE_PATH, JSON.stringify(baseline, null, 2) + '\n', 'utf-8');
  }

  if (violations.length > 0) {
    console.error(
      `[a11y-ratchet] FAIL: ${violations.length} page(s) with increased moderate/minor violations:`,
    );
    for (const v of violations) {
      console.error(
        `  ${v.label}: moderate ${v.baseline.moderate}→${v.observed.moderate} (+${v.delta.moderate}), ` +
          `minor ${v.baseline.minor}→${v.observed.minor} (+${v.delta.minor})`,
      );
    }
    console.error('');
    console.error('[a11y-ratchet] To ratchet DOWN: fix the violations, re-run a11y tests,');
    console.error('[a11y-ratchet] and commit the updated baseline with lower counts.');
    console.error('[a11y-ratchet] To accept the increase (e.g. new page added):');
    console.error('[a11y-ratchet]   UPDATE_BASELINE=1 node scripts/check_a11y_violation_ratchet.mjs ...');
    exit(1);
  }

  // Check for improvements — pages where counts dropped.
  const improvements = [];
  for (const [label, observedCounts] of observed) {
    const baselineEntry = pages[label];
    if (!baselineEntry || baselineEntry.moderate === -1) continue;
    const modDelta = observedCounts.moderate - baselineEntry.moderate;
    const minDelta = observedCounts.minor - baselineEntry.minor;
    if (modDelta < 0 || minDelta < 0) {
      improvements.push({ label, modDelta, minDelta });
    }
  }

  console.log(
    `[a11y-ratchet] OK — ${observed.size} page(s) audited, 0 regressions.`,
  );
  if (improvements.length > 0) {
    console.log(`[a11y-ratchet] ${improvements.length} page(s) improved — update the baseline to ratchet DOWN:`);
    for (const imp of improvements) {
      console.log(`  ${imp.label}: moderate ${imp.modDelta}, minor ${imp.minDelta}`);
    }
    console.log('[a11y-ratchet]   re-run with E2E_A11Y_RATCHET_OUTPUT set, then commit the updated baseline.');
  }
  exit(0);
}

main().catch((err) => {
  console.error(`[a11y-ratchet] unexpected error: ${err.message}`);
  exit(2);
});
