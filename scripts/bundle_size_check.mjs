#!/usr/bin/env node
/**
 * Phase 228.F2.30 — Bundle-size budget gate.
 *
 * After `npm run build`, this script:
 *
 *   1. Walks `frontend/dist/assets/` for `*.js` + `*.css` chunks.
 *   2. Computes their gzipped sizes.
 *   3. Compares against a baseline JSON
 *      (`frontend/.bundle-size-baseline.json`) checked into git.
 *   4. Emits a markdown summary table.
 *   5. Exits 1 if the *delta* between current and baseline exceeds
 *      30 KB gzipped (the F2 spec gate); 0 otherwise.
 *
 * Usage:
 *
 *     # Update the baseline (post-merge, after a known-good build).
 *     UPDATE_BASELINE=1 node scripts/bundle_size_check.mjs
 *
 *     # Gate (default — fails on >30 KB delta).
 *     node scripts/bundle_size_check.mjs
 *
 * Why a script vs a CI action: the GitHub-hosted bundle-size actions
 * (e.g. `andresz1/size-limit-action`) require a `size-limit` config
 * that itself drives the build.  Our pipeline already builds via
 * `npm run build`; this script reads the existing build output and
 * stays decoupled from any third-party CI tool.
 */
import { readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import path from 'node:path';
import process from 'node:process';

const REPO_ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const DIST_DIR = path.join(REPO_ROOT, 'frontend', 'dist', 'assets');
const BASELINE_PATH = path.join(
  REPO_ROOT, 'frontend', '.bundle-size-baseline.json',
);
// Phase 228.F2.30 — 30 KB gzipped delta.
const MAX_DELTA_BYTES = 30 * 1024;

async function listAssets() {
  let files = [];
  try {
    files = await readdir(DIST_DIR);
  } catch (err) {
    console.error(
      `[bundle-size-check] cannot read ${DIST_DIR}: ${(err).message}`,
    );
    console.error('[bundle-size-check] run `npm run build` first');
    process.exit(2);
  }
  return files.filter((f) => /\.(js|css)$/.test(f));
}

async function gzippedSize(filePath) {
  const buf = await readFile(filePath);
  return gzipSync(buf).length;
}

async function loadBaseline() {
  try {
    const raw = await readFile(BASELINE_PATH, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { total_gzipped_bytes: 0, files: {} };
  }
}

async function main() {
  const files = await listAssets();
  const sizes = {};
  let total = 0;
  for (const f of files) {
    const fp = path.join(DIST_DIR, f);
    const s = await stat(fp);
    if (!s.isFile()) continue;
    const gz = await gzippedSize(fp);
    sizes[f] = gz;
    total += gz;
  }

  if (process.env.UPDATE_BASELINE === '1') {
    await writeFile(
      BASELINE_PATH,
      JSON.stringify(
        { total_gzipped_bytes: total, files: sizes },
        null, 2,
      ) + '\n',
    );
    console.log(
      `[bundle-size-check] baseline updated: total=${total} bytes`,
    );
    return;
  }

  const baseline = await loadBaseline();

  // Phase 228.F2.DoD.6 audit fix — first-baseline guard.  The
  // initial committed baseline is a 0-byte placeholder; without
  // this guard the very first PR with the gate enabled would
  // fail because `total - 0 > 30 KB`.  Treat any baseline below
  // 1 KB as the placeholder (a real bundle has hundreds of KB
  // gzipped) and skip the gate with a re-baseline instruction.
  // Once a real baseline lands via `UPDATE_BASELINE=1`, this
  // branch is permanently bypassed.
  const FIRST_RUN_THRESHOLD_BYTES = 1024;
  if (baseline.total_gzipped_bytes < FIRST_RUN_THRESHOLD_BYTES) {
    console.warn(
      `[bundle-size-check] WARN: baseline is ${baseline.total_gzipped_bytes} bytes ` +
      `(below ${FIRST_RUN_THRESHOLD_BYTES} B first-run threshold). ` +
      `Skipping the gate.  Re-baseline post-merge via:\n` +
      `    UPDATE_BASELINE=1 node scripts/bundle_size_check.mjs`,
    );
    if (process.env.GITHUB_STEP_SUMMARY) {
      await writeFile(
        process.env.GITHUB_STEP_SUMMARY,
        `## Phase 228.F2.30 — bundle-size delta\n\n` +
        `**First run** — baseline placeholder is ${baseline.total_gzipped_bytes} bytes. ` +
        `Current bundle is ${total} bytes. ` +
        `Re-baseline post-merge to activate the gate.\n`,
        { flag: 'a' },
      );
    }
    return;
  }

  const delta = total - baseline.total_gzipped_bytes;

  // Markdown summary for GITHUB_STEP_SUMMARY.
  const lines = [];
  lines.push('## Phase 228.F2.30 — bundle-size delta');
  lines.push('');
  lines.push(`| | Total (gzipped) |`);
  lines.push(`| --- | ---: |`);
  lines.push(`| Baseline | ${baseline.total_gzipped_bytes} bytes |`);
  lines.push(`| Current | ${total} bytes |`);
  lines.push(`| **Delta** | **${delta >= 0 ? '+' : ''}${delta} bytes** |`);
  lines.push(`| Budget | ±${MAX_DELTA_BYTES} bytes |`);
  lines.push('');
  console.log(lines.join('\n'));

  if (process.env.GITHUB_STEP_SUMMARY) {
    await writeFile(
      process.env.GITHUB_STEP_SUMMARY,
      lines.join('\n') + '\n',
      { flag: 'a' },
    );
  }

  if (delta > MAX_DELTA_BYTES) {
    console.error(
      `[bundle-size-check] FAIL: delta ${delta} > budget ${MAX_DELTA_BYTES} bytes`,
    );
    process.exit(1);
  }
  console.log('[bundle-size-check] OK');
}

main().catch((err) => {
  console.error('[bundle-size-check] error', err);
  process.exit(2);
});
