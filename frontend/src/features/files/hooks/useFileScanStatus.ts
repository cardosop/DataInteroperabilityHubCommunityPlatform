/**
 * Polls lightweight scan status while the file is pending malware scan (Phase 260.3.D).
 */

import { useEffect, useState } from 'react';
import { fileService } from '../services/fileService';
import type { FileScanStatus } from '../../../shared/types/files';
import {
  FILE_SCAN_STATUS_POLL_INTERVAL_MS,
  shouldContinuePollingFileScanStatus,
} from '../utils/fileScanStatusPoll';

export interface UseFileScanStatusResult {
  scanStatus: FileScanStatus | string | null;
  scannedAt: string | null;
  error: unknown;
  /** True until the first request for this fileId/enabled combo settles. */
  isLoading: boolean;
}

export function useFileScanStatus(
  fileId: string | null,
  options?: { enabled?: boolean }
): UseFileScanStatusResult {
  const enabled = options?.enabled !== false;
  const [scanStatus, setScanStatus] = useState<FileScanStatus | string | null>(null);
  const [scannedAt, setScannedAt] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!fileId || !enabled) {
      setScanStatus(null);
      setScannedAt(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    let intervalId: ReturnType<typeof setInterval> | undefined;
    let firstPending = true;
    setIsLoading(true);
    setError(null);

    const tick = async () => {
      try {
        const data = await fileService.getScanStatus(fileId);
        if (cancelled) return;
        setScanStatus(data.scan_status);
        setScannedAt(data.scanned_at ?? null);
        setError(null);
        if (firstPending) {
          firstPending = false;
          setIsLoading(false);
        }
        if (!shouldContinuePollingFileScanStatus(data.scan_status)) {
          if (intervalId !== undefined) {
            clearInterval(intervalId);
            intervalId = undefined;
          }
        }
      } catch (e) {
        if (!cancelled) {
          setError(e);
          if (firstPending) {
            firstPending = false;
            setIsLoading(false);
          }
        }
      }
    };

    void tick();
    intervalId = setInterval(() => {
      void tick();
    }, FILE_SCAN_STATUS_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalId !== undefined) {
        clearInterval(intervalId);
      }
    };
  }, [fileId, enabled]);

  return { scanStatus, scannedAt, error, isLoading };
}
