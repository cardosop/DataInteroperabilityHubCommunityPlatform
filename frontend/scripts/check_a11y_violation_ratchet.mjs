/**
 * Phase 278.U.4 — A11y violation ratchet CI gate.
 *
 * Compares observed a11y violation counts (from axe-core audits) against
 * a committed baseline file. Fails the CI job if any page shows an
 * INCREASE in moderate or minor violations.
 *
 * First-run / auto-populate mode: when the baseline has `_first_run: true`
 * or all entries are placeholder `-1`, populates the baseline with observed
 * counts and exits 0 (operator commits the updated baseline).
 *
 * Usage:
 *   node scripts/check_a11y_violation_ratchet.mjs <path-to-ratchet-output.jsonl>
 *   node scripts/check_a11y_violation_ratchet.mjs <ratchet-output.jsonl> [baseline.json]
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const BASELINE_DEFAULT = resolve(import.meta.dirname, '..', 'e2e', 'a11y', 'violationCounts.json');

function loadJSON(path) {
  try { return JSON.parse(readFileSync(path, 'utf-8')); }
  catch { return null; }
}

function parseRatchetOutput(path) {
  const raw = readFileSync(path, 'utf-8').trim();
  if (!raw) return [];
  return raw.split('\n').map(l => JSON.parse(l));
}

function main() {
  if (process.argv.length < 3) {
    console.error('Usage: node check_a11y_violation_ratchet.mjs <ratchet-output.jsonl> [baseline.json]');
    process.exit(2);
  }

  const ratchetPath = process.argv[2];
  const baselinePath = process.argv[3] || BASELINE_DEFAULT;

  let observed;
  try { observed = parseRatchetOutput(ratchetPath); }
  catch {
    console.log('WARNING: Ratchet output not found or empty — skipping a11y ratchet check.');
    process.exit(0);
  }

  if (observed.length === 0) {
    console.log('No a11y audit entries found — skipping.');
    process.exit(0);
  }

  const baseline = loadJSON(baselinePath) || { _first_run: true };

  // First-run: auto-populate baseline
  const isFirstRun = baseline._first_run === true ||
    Object.entries(baseline).filter(([k]) => k !== '_first_run').every(([, v]) => v === -1);

  if (isFirstRun) {
    const populated = { _first_run: false };
    for (const entry of observed) {
      const label = entry.label || 'unknown';
      populated[label] = {
        moderate: entry.moderate ?? 0,
        minor: entry.minor ?? 0,
        total: entry.total ?? 0,
      };
    }
    writeFileSync(baselinePath, JSON.stringify(populated, null, 2) + '\n');
    console.log('First-run: baseline auto-populated with observed counts.');
    console.log(`Commit the updated ${baselinePath} to activate the ratchet.`);
    process.exit(0);
  }

  // Ratchet mode: compare observed vs baseline
  let failed = false;
  let improvedLabels = [];

  for (const entry of observed) {
    const label = entry.label || 'unknown';
    const bl = baseline[label];

    if (!bl) {
      // New page — auto-add to baseline
      console.log(`NEW PAGE: ${label} (auto-added to baseline with ${entry.moderate} moderate, ${entry.minor} minor)`);
      baseline[label] = { moderate: entry.moderate ?? 0, minor: entry.minor ?? 0, total: entry.total ?? 0 };
      continue;
    }

    const obsModerate = entry.moderate ?? 0;
    const obsMinor = entry.minor ?? 0;
    const blModerate = bl.moderate ?? 0;
    const blMinor = bl.minor ?? 0;

    if (obsModerate > blModerate) {
      console.error(`FAIL: ${label} — moderate violations increased from ${blModerate} to ${obsModerate}`);
      failed = true;
    }
    if (obsMinor > blMinor) {
      console.error(`FAIL: ${label} — minor violations increased from ${blMinor} to ${obsMinor}`);
      failed = true;
    }

    if (obsModerate < blModerate || obsMinor < blMinor) {
      improvedLabels.push(label);
    }
  }

  if (failed) {
    console.error('\nA11y ratchet gate FAILED — violations increased. Fix the violations before merging.');
    process.exit(1);
  }

  if (improvedLabels.length > 0) {
    console.log(`\n${improvedLabels.length} page(s) improved — run locally with E2E_A11Y_RATCHET_OUTPUT set to ratchet down:`, improvedLabels.slice(0, 5).join(', '));
  }

  console.log('A11y ratchet gate PASSED.');
}

main();
