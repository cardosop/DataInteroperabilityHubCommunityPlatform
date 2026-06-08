/**
 * Scan-status polling helpers (Phase 260.3.D).
 * Keeps interval / termination rules testable without stubbing HTTP.
 */

import { FileScanStatus } from '../../../shared/types/files';

export const FILE_SCAN_STATUS_POLL_INTERVAL_MS = 2000;

/** While true, the UI may poll GET /files/{id}/scan-status/ every 2s. */
export function shouldContinuePollingFileScanStatus(
  scanStatus: string | null | undefined
): boolean {
  return scanStatus === FileScanStatus.PENDING_SCAN;
}
