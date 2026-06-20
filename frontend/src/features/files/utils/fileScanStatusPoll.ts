/**
 * Scan-status polling helpers (Phase 260.3.D).
 *
 * Adaptive polling: fast cadence (2s) for the first 30s, then 5s up to
 * the SLA estimate, then 10s for overdue files. Reduces load on the
 * scan-status endpoint while maintaining responsiveness for quick scans.
 */

import { FileScanStatus } from '../../../shared/types/files';

/** Fast-poll cadence for the first ADAPTIVE_FAST_WINDOW_MS (2s). */
export const FILE_SCAN_STATUS_POLL_INTERVAL_MS = 2000;
/** Medium cadence between fast window and SLA estimate (5s). */
export const FILE_SCAN_STATUS_POLL_MEDIUM_MS = 5000;
/** Slow cadence once a file is past its SLA estimate (10s). */
export const FILE_SCAN_STATUS_POLL_SLOW_MS = 10000;
/** Switch from fast to medium cadence after 30s of polling. */
export const FILE_SCAN_POLL_FAST_WINDOW_MS = 30_000;

/**
 * Return the appropriate poll interval for the given elapsed milliseconds.
 *
 * - 0 … ``FILE_SCAN_POLL_FAST_WINDOW_MS`` → fast (2s)
 * - fast window … ``slaEstimateMs`` → medium (5s)
 * - past ``slaEstimateMs`` → slow (10s)
 */
export function adaptivePollIntervalMs(
  elapsedMs: number,
  slaEstimateMs: number = FILE_SCAN_POLL_FAST_WINDOW_MS,
): number {
  if (elapsedMs <= FILE_SCAN_POLL_FAST_WINDOW_MS) {
    return FILE_SCAN_STATUS_POLL_INTERVAL_MS;
  }
  if (elapsedMs <= Math.max(slaEstimateMs, FILE_SCAN_POLL_FAST_WINDOW_MS)) {
    return FILE_SCAN_STATUS_POLL_MEDIUM_MS;
  }
  return FILE_SCAN_STATUS_POLL_SLOW_MS;
}

/** While true, the UI may poll GET /files/{id}/scan-status/. */
export function shouldContinuePollingFileScanStatus(
  scanStatus: string | null | undefined,
): boolean {
  return scanStatus === FileScanStatus.PENDING_SCAN;
}
