/**
 * Phase 250.6.C TDD pins for `useAssetWorkflowStatus` — pure
 * function `computePollInterval` covering the F2-4 backoff
 * schedule (1.5s → 5s → 15s after 30s / 2min of RUNNING).
 *
 * The hook itself is integration-tested by the E2E spec at
 * `frontend/e2e/journeys/dpo/asset-workflow-progress.spec.ts`
 * (Phase 250.6.C.6) — Vitest doesn't add value over E2E for the
 * React Query plumbing (the schedule is the load-bearing logic
 * here and is already a pure function). The Vitest pin here
 * locks the schedule in isolation so future edits to the cutoff
 * thresholds break this test, not the slower E2E run.
 */
import { describe, expect, it } from 'vitest';

import {
  POLL_BACKOFF_MEDIUM_AFTER_MS,
  POLL_BACKOFF_SLOW_AFTER_MS,
  POLL_INTERVAL_FAST_MS,
  POLL_INTERVAL_MEDIUM_MS,
  POLL_INTERVAL_SLOW_MS,
  computePollInterval,
} from './useAssetWorkflowStatus';

describe('computePollInterval (F2-4 backoff schedule)', () => {
  const NOW = 1_700_000_000_000; // fixed wall-clock so tests are deterministic

  it('returns the fast interval when started_at is null', () => {
    expect(computePollInterval(null, NOW)).toBe(POLL_INTERVAL_FAST_MS);
    expect(computePollInterval(undefined, NOW)).toBe(POLL_INTERVAL_FAST_MS);
  });

  it('returns the fast interval when started_at is malformed', () => {
    expect(computePollInterval('not-a-date', NOW)).toBe(POLL_INTERVAL_FAST_MS);
  });

  it('returns the fast interval (1.5s) inside the first 30s window', () => {
    const startedAt = new Date(NOW - 5_000).toISOString(); // 5s ago
    expect(computePollInterval(startedAt, NOW)).toBe(POLL_INTERVAL_FAST_MS);
  });

  it('returns the medium interval (5s) at the 30s boundary', () => {
    const startedAt = new Date(
      NOW - POLL_BACKOFF_MEDIUM_AFTER_MS,
    ).toISOString();
    expect(computePollInterval(startedAt, NOW)).toBe(POLL_INTERVAL_MEDIUM_MS);
  });

  it('returns the medium interval (5s) inside the 30s-120s window', () => {
    const startedAt = new Date(NOW - 60_000).toISOString(); // 60s ago
    expect(computePollInterval(startedAt, NOW)).toBe(POLL_INTERVAL_MEDIUM_MS);
  });

  it('returns the slow interval (15s) at the 2-minute boundary', () => {
    const startedAt = new Date(
      NOW - POLL_BACKOFF_SLOW_AFTER_MS,
    ).toISOString();
    expect(computePollInterval(startedAt, NOW)).toBe(POLL_INTERVAL_SLOW_MS);
  });

  it('returns the slow interval (15s) for very long-running workflows', () => {
    const startedAt = new Date(NOW - 30 * 60_000).toISOString(); // 30 min ago
    expect(computePollInterval(startedAt, NOW)).toBe(POLL_INTERVAL_SLOW_MS);
  });
});
