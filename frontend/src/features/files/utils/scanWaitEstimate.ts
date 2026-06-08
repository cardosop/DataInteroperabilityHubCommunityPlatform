/**
 * Phase 260.3.H.1 — estimated wait until the malware scan completes.
 *
 * Drives the customer-education banner copy ("Scanning in progress —
 * about 30 seconds remaining…"). The estimate is a deterministic
 * size-tiered SLA model: scans are bounded by the slowest expected
 * processing time per tier rather than a moving average, which keeps
 * the UI honest under cold-cache / startup conditions and avoids the
 * flicker that historical-medians introduce.
 *
 * Tiers (rough p95 envelope from the malware-scan service runbook):
 *   - small  (< 100 MiB)       → 60 s
 *   - medium (100 MiB – 1 GiB) → 180 s
 *   - large  (≥ 1 GiB)         → 360 s
 *
 * The estimator returns ``null`` for terminal scan-status values
 * because the banner is only meaningful while a scan is in flight.
 */

import { FileScanStatus } from '../../../shared/types/files';

export const SCAN_SLA_SMALL_MS = 60_000;
export const SCAN_SLA_MEDIUM_MS = 180_000;
export const SCAN_SLA_LARGE_MS = 360_000;

/** Files at this size or larger graduate from "small" → "medium" tier. */
export const SCAN_SLA_MEDIUM_FILE_BYTES = 100 * 1024 * 1024;
/** Files at this size or larger graduate from "medium" → "large" tier. */
export const SCAN_SLA_LARGE_FILE_BYTES = 1024 * 1024 * 1024;

export type ScanWaitTier = 'small' | 'medium' | 'large';

export interface ScanWaitEstimate {
  /** Milliseconds remaining until the scan SLA elapses (clamped ≥ 0). */
  remainingMs: number;
  /** Milliseconds since the file was uploaded. */
  elapsedMs: number;
  /** Total SLA budget for this file's size tier. */
  totalSlaMs: number;
  /** ``true`` when ``elapsedMs >= totalSlaMs`` — banner switches copy. */
  overdue: boolean;
  /** Which size tier the file fell into. */
  tier: ScanWaitTier;
}

interface EstimateInput {
  /** ``File.scan_status`` from the catalog row. */
  scanStatus: string;
  /** ``File.size`` in bytes. Negative / non-finite values fall back to small. */
  size: number;
  /**
   * ``File.uploaded_at`` (or ``created_at``) ISO-8601 string. Null /
   * empty / unparseable values fall back to the full-SLA remaining
   * (callers see "about 60 s left" rather than NaN or Infinity).
   */
  uploadedAt: string | null;
  /** Injectable for deterministic testing; defaults to ``Date.now()``. */
  now?: number;
}

const TERMINAL_STATUSES: ReadonlySet<string> = new Set<string>([
  FileScanStatus.CLEAN,
  FileScanStatus.INFECTED,
  FileScanStatus.SCAN_ERROR,
  FileScanStatus.SCAN_UNAVAILABLE,
]);

function tierFor(size: number): ScanWaitTier {
  if (!Number.isFinite(size) || size < SCAN_SLA_MEDIUM_FILE_BYTES) return 'small';
  if (size < SCAN_SLA_LARGE_FILE_BYTES) return 'medium';
  return 'large';
}

function slaForTier(tier: ScanWaitTier): number {
  if (tier === 'medium') return SCAN_SLA_MEDIUM_MS;
  if (tier === 'large') return SCAN_SLA_LARGE_MS;
  return SCAN_SLA_SMALL_MS;
}

function parseTimestamp(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return null;
  return ms;
}

export function estimateScanWait(input: EstimateInput): ScanWaitEstimate | null {
  if (TERMINAL_STATUSES.has(input.scanStatus)) return null;

  const tier = tierFor(input.size);
  const totalSlaMs = slaForTier(tier);
  const now = input.now ?? Date.now();
  const uploadedMs = parseTimestamp(input.uploadedAt);

  // No / bad timestamp → assume the upload just landed; return the
  // full-SLA remaining so the banner shows a number, not "NaN s".
  const elapsedMs = uploadedMs === null ? 0 : Math.max(0, now - uploadedMs);
  const remainingMs = Math.max(0, totalSlaMs - elapsedMs);
  const overdue = elapsedMs >= totalSlaMs;

  return { remainingMs, elapsedMs, totalSlaMs, overdue, tier };
}
