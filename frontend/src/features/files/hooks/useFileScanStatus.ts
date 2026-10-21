/**
 * Polls lightweight scan status while the file is pending malware scan (Phase 260.3.D).
 *
 * Phase 260.3 improvement: adaptive polling — fast (2s) for the first 30s,
 * medium (5s) up to SLA estimate, slow (10s) for overdue files. Reduces
 * endpoint load while maintaining responsiveness for quick scans.
 */

import { useEffect, useState } from 'react';
import { fileService } from '../services/fileService';
import type { FileScanStatus } from '../../../shared/types/files';
import {
  adaptivePollIntervalMs,
  FILE_SCAN_POLL_FAST_WINDOW_MS,
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
  options?: { enabled?: boolean; slaEstimateMs?: number }
): UseFileScanStatusResult {
  const enabled = options?.enabled !== false;
  const slaEstimateMs = options?.slaEstimateMs ?? FILE_SCAN_POLL_FAST_WINDOW_MS;
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
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let firstPending = true;
    const startTime = Date.now();
    setIsLoading(true);
    setError(null);

    const scheduleNext = (delayMs: number) => {
      if (cancelled) return;
      timeoutId = setTimeout(() => {
        void tick();
      }, delayMs);
    };

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
          return; // stop polling — terminal status reached
        }
        // Schedule next poll with adaptive interval
        const elapsed = Date.now() - startTime;
        scheduleNext(adaptivePollIntervalMs(elapsed, slaEstimateMs));
      } catch (e) {
        if (!cancelled) {
          setError(e);
          if (firstPending) {
            firstPending = false;
            setIsLoading(false);
          }
          // Retry on error with fast interval
          scheduleNext(adaptivePollIntervalMs(Date.now() - startTime, slaEstimateMs));
        }
      }
    };

    void tick();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
      }
    };
  }, [fileId, enabled, slaEstimateMs]);

  return { scanStatus, scannedAt, error, isLoading };
}
