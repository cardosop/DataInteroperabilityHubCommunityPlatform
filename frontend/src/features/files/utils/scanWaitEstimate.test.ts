/**
 * scanWaitEstimate tests — Phase 260.3.H.1.
 *
 * Pure-function tests for the "how much longer until the malware
 * scan completes?" estimator that powers the customer-education
 * banner. No HTTP, no React, no DOM — just a deterministic
 * size-tiered SLA model + the elapsed time since upload.
 *
 * Engineering invariants under test:
 *   - SLA tiers are size-stratified (small / medium / large) so a
 *     2 MiB file isn't told "60 seconds" the same way a 4 GiB file is.
 *   - The estimator is monotonic: more elapsed time always reduces
 *     remaining time (never increases).
 *   - Past-SLA elapsed times clamp to zero — we never advertise a
 *     negative wait. Instead the result is flagged ``overdue`` so
 *     the banner can switch copy ("scan is taking longer than
 *     usual…").
 *   - Terminal states (CLEAN / INFECTED / SCAN_ERROR / SCAN_UNAVAILABLE)
 *     return ``null`` — the banner is for in-flight scans only.
 *   - Missing / malformed timestamps fall back to the full-SLA
 *     remaining (no NaN, no Infinity, no exception).
 */

import { describe, expect, it } from 'vitest';

import { FileScanStatus } from '../../../shared/types/files';
import {
  SCAN_SLA_LARGE_FILE_BYTES,
  SCAN_SLA_LARGE_MS,
  SCAN_SLA_MEDIUM_FILE_BYTES,
  SCAN_SLA_MEDIUM_MS,
  SCAN_SLA_SMALL_MS,
  estimateScanWait,
  type ScanWaitEstimate,
} from './scanWaitEstimate';

const NOW = Date.parse('2026-05-06T12:00:00Z');

function input(overrides: {
  scanStatus?: string;
  size?: number;
  uploadedAt?: string | null;
} = {}) {
  // Use ``in`` rather than ``??`` so an explicit ``uploadedAt: null``
  // override is honoured (??-fallback would treat null as missing).
  const uploadedAt =
    'uploadedAt' in overrides
      ? overrides.uploadedAt
      : new Date(NOW - 5_000).toISOString();
  return {
    scanStatus: overrides.scanStatus ?? FileScanStatus.PENDING_SCAN,
    size: overrides.size ?? 1024,
    uploadedAt: uploadedAt as string | null,
    now: NOW,
  };
}

describe('estimateScanWait — terminal states', () => {
  it.each([
    FileScanStatus.CLEAN,
    FileScanStatus.INFECTED,
    FileScanStatus.SCAN_ERROR,
    FileScanStatus.SCAN_UNAVAILABLE,
  ])('returns null for terminal status %s', (status) => {
    expect(estimateScanWait(input({ scanStatus: status }))).toBeNull();
  });
});

describe('estimateScanWait — SLA tiers', () => {
  it('uses the small-file SLA for files at the small/medium boundary', () => {
    // size === 0 is in the "small" tier; SLA_SMALL_MS is the budget.
    const r = estimateScanWait(input({ size: 0, uploadedAt: new Date(NOW).toISOString() }));
    expect(r?.totalSlaMs).toBe(SCAN_SLA_SMALL_MS);
    expect(r?.tier).toBe('small');
  });

  it('uses the medium-file SLA when size crosses SCAN_SLA_MEDIUM_FILE_BYTES', () => {
    const r = estimateScanWait(
      input({
        size: SCAN_SLA_MEDIUM_FILE_BYTES,
        uploadedAt: new Date(NOW).toISOString(),
      })
    );
    expect(r?.totalSlaMs).toBe(SCAN_SLA_MEDIUM_MS);
    expect(r?.tier).toBe('medium');
  });

  it('uses the large-file SLA when size crosses SCAN_SLA_LARGE_FILE_BYTES', () => {
    const r = estimateScanWait(
      input({
        size: SCAN_SLA_LARGE_FILE_BYTES,
        uploadedAt: new Date(NOW).toISOString(),
      })
    );
    expect(r?.totalSlaMs).toBe(SCAN_SLA_LARGE_MS);
    expect(r?.tier).toBe('large');
  });
});

describe('estimateScanWait — remaining time arithmetic', () => {
  it('returns full SLA at zero elapsed', () => {
    const r = estimateScanWait(
      input({ size: 1024, uploadedAt: new Date(NOW).toISOString() })
    );
    expect(r?.remainingMs).toBe(SCAN_SLA_SMALL_MS);
    expect(r?.elapsedMs).toBe(0);
    expect(r?.overdue).toBe(false);
  });

  it('subtracts the elapsed time from the SLA', () => {
    const elapsed = SCAN_SLA_SMALL_MS / 2;
    const r = estimateScanWait(
      input({ size: 1024, uploadedAt: new Date(NOW - elapsed).toISOString() })
    );
    expect(r?.remainingMs).toBe(SCAN_SLA_SMALL_MS - elapsed);
    expect(r?.elapsedMs).toBe(elapsed);
  });

  it('clamps remaining to 0 and flags overdue when elapsed exceeds the SLA', () => {
    const r = estimateScanWait(
      input({
        size: 1024,
        uploadedAt: new Date(NOW - SCAN_SLA_SMALL_MS - 60_000).toISOString(),
      })
    );
    expect(r?.remainingMs).toBe(0);
    expect(r?.overdue).toBe(true);
  });

  it('is monotonic: more elapsed time never increases remaining', () => {
    const a = estimateScanWait(
      input({ size: 1024, uploadedAt: new Date(NOW - 1_000).toISOString() })
    );
    const b = estimateScanWait(
      input({ size: 1024, uploadedAt: new Date(NOW - 5_000).toISOString() })
    );
    expect((b?.remainingMs ?? 0)).toBeLessThanOrEqual(a?.remainingMs ?? 0);
  });
});

describe('estimateScanWait — input robustness', () => {
  it('falls back to full-SLA remaining for null uploadedAt', () => {
    const r = estimateScanWait(input({ uploadedAt: null }));
    expect(r?.remainingMs).toBe(SCAN_SLA_SMALL_MS);
    expect(r?.elapsedMs).toBe(0);
  });

  it('falls back for an empty-string timestamp', () => {
    const r = estimateScanWait(input({ uploadedAt: '' }));
    expect(r?.remainingMs).toBe(SCAN_SLA_SMALL_MS);
  });

  it('falls back for an unparseable timestamp', () => {
    const r = estimateScanWait(input({ uploadedAt: 'not-a-date' }));
    expect(r?.remainingMs).toBe(SCAN_SLA_SMALL_MS);
  });

  it('treats negative file size as the small tier (defensive)', () => {
    const r = estimateScanWait(input({ size: -1 }));
    expect(r?.tier).toBe('small');
  });

  it('returns a typed result; never throws', () => {
    // Runtime-shape check: we want a stable contract for callers.
    const r = estimateScanWait(input()) as ScanWaitEstimate;
    expect(r).toEqual(
      expect.objectContaining({
        remainingMs: expect.any(Number),
        elapsedMs: expect.any(Number),
        totalSlaMs: expect.any(Number),
        overdue: expect.any(Boolean),
        tier: expect.stringMatching(/^(small|medium|large)$/),
      })
    );
  });
});
