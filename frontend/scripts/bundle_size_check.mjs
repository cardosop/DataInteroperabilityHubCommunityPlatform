/**
 * Phase 278.T.1 — Bundle-size budget gate.
 *
 * Compares the current `npm run build` output against
 * `frontend/.bundle-size-baseline.json`. Fails if the total gzipped
 * delta exceeds the budget (30 KB).
 *
 * Re-baseline after merging significant features:
 *   UPDATE_BASELINE=1 node scripts/bundle_size_check.mjs
 */
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { globSync } from 'glob';
import { gzipSync } from 'node:zlib';
import { resolve, relative, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const BASELINE_PATH = resolve(ROOT, '.bundle-size-baseline.json');
const DIST_DIR = resolve(ROOT, 'dist');
const DELTA_BUDGET_BYTES = 30 * 1024; // 30 KB gzipped
const FIRST_RUN_THRESHOLD_BYTES = 1024;

function getCurrentSizes() {
  const files = {};
  let total = 0;
  const jsCss = globSync(`${DIST_DIR}/**/*.{js,css}`);
  let phase232Programme = 0;
  for (const f of jsCss) {
    const raw = readFileSync(f);
    const gzipped = gzipSync(raw).length;
    const rel = relative(ROOT, f);
    files[rel] = gzipped;
    total += gzipped;
    // Phase 232 programme chunk: stabilise after initial baseline
    if (rel.includes('phase232') && rel.includes('programme')) {
      phase232Programme += gzipped;
    }
  }
  return { files, total, phase232Programme };
}

function loadBaseline() {
  try {
    const raw = readFileSync(BASELINE_PATH, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function main() {
  const current = getCurrentSizes();

  // Re-baseline mode
  if (process.env.UPDATE_BASELINE === '1') {
    const baseline = {
      _note: `Phase 278.T.1 baseline — delta budget: ${DELTA_BUDGET_BYTES} bytes (${(DELTA_BUDGET_BYTES / 1024).toFixed(0)} KB) gzipped. Re-baseline: UPDATE_BASELINE=1 node scripts/bundle_size_check.mjs`,
      total_gzipped_bytes: current.total,
      phase232_programme_gzipped_bytes: current.phase232Programme,
      files: current.files,
    };
    writeFileSync(BASELINE_PATH, JSON.stringify(baseline, null, 2) + '\n');
    console.log(`Baseline written: ${current.total} bytes total, ${Object.keys(current.files).length} files`);
    return;
  }

  const baseline = loadBaseline();
  if (!baseline || !baseline.total_gzipped_bytes || baseline.total_gzipped_bytes < FIRST_RUN_THRESHOLD_BYTES) {
    console.log('No baseline or baseline too small (< 1 KB). Skipping check (first run or empty baseline).');
    process.exit(0);
  }

  const delta = current.total - baseline.total_gzipped_bytes;
  const deltaKB = (delta / 1024).toFixed(1);
  const pct = baseline.total_gzipped_bytes > 0
    ? ((delta / baseline.total_gzipped_bytes) * 100).toFixed(1)
    : '0.0';

  console.log(`Bundle size: current=${current.total} bytes, baseline=${baseline.total_gzipped_bytes} bytes, delta=${delta > 0 ? '+' : ''}${delta} bytes (${deltaKB} KB, ${pct}%)`);

  if (delta > DELTA_BUDGET_BYTES) {
    console.error(`ERROR: Bundle size grew by ${deltaKB} KB — exceeds ${DELTA_BUDGET_BYTES / 1024} KB budget.`);
    console.error('Review the build output for unexpectedly large chunks. To re-baseline:');
    console.error('  UPDATE_BASELINE=1 node scripts/bundle_size_check.mjs');
    process.exit(1);
  }

  if (delta < -DELTA_BUDGET_BYTES) {
    console.log(`Bundle size decreased by ${Math.abs(deltaKB)} KB — consider re-baselining to lock in the improvement.`);
  }

  console.log('Bundle size check PASSED.');
}

main();
