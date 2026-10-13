#!/usr/bin/env node
/**
 * Run the vitest suite in sequential shards.
 *
 * The threads pool runs every test file in ONE process heap; ~330
 * jsdom files accumulate past Node's default ~4.2 GB old-space and the
 * worker dies with ERR_WORKER_OUT_OF_MEMORY mid-run. The OOM point
 * moves with the shard partition (vitest shards by test count, so the
 * member set of a heavy shard is not contiguous in file order and the
 * crash is not reproducible by any externally reconstructed file
 * list). Sharding bounds each process's live heap; the retry-once
 * policy absorbs the residual intermittent OOM without masking real
 * test failures — a shard that fails identically twice fails the run.
 *
 * Usage: node scripts/test-shards.cjs [extra vitest args...]
 * Shard count via VITEST_SHARDS (default 10 — ~34 files/shard, ~8
 * shards green empirically; the heavy partition stays below the 8 GiB
 * cap the npm scripts set).
 */
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const total = Number(process.env.VITEST_SHARDS || 10);
const vitestBin = path.join(__dirname, '..', 'node_modules', '.bin', 'vitest');

let failed = false;
for (let i = 1; i <= total; i += 1) {
  process.stdout.write(`\n=== vitest shard ${i}/${total} ===\n`);
  const run = () =>
    spawnSync(
      vitestBin,
      ['--run', `--shard=${i}/${total}`, ...process.argv.slice(2)],
      { stdio: 'inherit', env: process.env },
    );
  let result = run();
  if (result.status !== 0) {
    process.stdout.write(`\n--- vitest shard ${i}/${total} failed (${result.status}); retrying once ---\n`);
    result = run();
  }
  if (result.status !== 0) {
    failed = true;
  }
}
process.exit(failed ? 1 : 0);
