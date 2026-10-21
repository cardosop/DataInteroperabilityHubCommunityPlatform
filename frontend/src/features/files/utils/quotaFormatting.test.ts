/**
 * quotaFormatting helpers — pure unit tests for Phase 260.4.G.
 *
 * Pinning the severity thresholds + bytes formatter as unit tests
 * lets future refactors land without breaking the load-bearing
 * boundaries (80 / 90 / 95) that the meter UX depends on.
 */
import { describe, expect, it } from 'vitest';

import {
  formatBytes,
  QUOTA_DANGER_THRESHOLD_PERCENT,
  QUOTA_UPGRADE_CTA_THRESHOLD_PERCENT,
  QUOTA_WARN_THRESHOLD_PERCENT,
  severityForQuota,
} from './quotaFormatting';

describe('quota threshold constants (Phase 260.4.G spec)', () => {
  it('matches the spec thresholds', () => {
    expect(QUOTA_WARN_THRESHOLD_PERCENT).toBe(80);
    expect(QUOTA_UPGRADE_CTA_THRESHOLD_PERCENT).toBe(90);
    expect(QUOTA_DANGER_THRESHOLD_PERCENT).toBe(95);
  });
});

describe('severityForQuota', () => {
  it('returns "normal" for usage at or below 80%', () => {
    expect(severityForQuota(0)).toBe('normal');
    expect(severityForQuota(50)).toBe('normal');
    expect(severityForQuota(80)).toBe('normal'); // strictly > to flip
  });

  it('returns "warn" for usage above 80% but at or below 95%', () => {
    expect(severityForQuota(80.01)).toBe('warn');
    expect(severityForQuota(90)).toBe('warn');
    expect(severityForQuota(95)).toBe('warn'); // strictly > to flip
  });

  it('returns "danger" for usage above 95%', () => {
    expect(severityForQuota(95.01)).toBe('danger');
    expect(severityForQuota(99.9)).toBe('danger');
    expect(severityForQuota(100)).toBe('danger');
  });

  it('returns "normal" when percentage is null/undefined (unlimited / unknown)', () => {
    expect(severityForQuota(null)).toBe('normal');
    expect(severityForQuota(undefined)).toBe('normal');
  });
});

describe('formatBytes', () => {
  it('formats bytes / KB / MB / GB / TB consistently', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1023)).toBe('1023 B');
    expect(formatBytes(1024)).toBe('1.0 KB');
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB');
    expect(formatBytes(1024 * 1024 * 1024)).toBe('1.0 GB');
    expect(formatBytes(1024 * 1024 * 1024 * 1024)).toBe('1.00 TB');
  });
});
