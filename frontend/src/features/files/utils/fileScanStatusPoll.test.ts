import { describe, expect, it } from 'vitest';
import { FileScanStatus } from '../../../shared/types/files';
import {
  FILE_SCAN_STATUS_POLL_INTERVAL_MS,
  shouldContinuePollingFileScanStatus,
} from './fileScanStatusPoll';

describe('fileScanStatusPoll', () => {
  it('uses 2s poll interval contract', () => {
    expect(FILE_SCAN_STATUS_POLL_INTERVAL_MS).toBe(2000);
  });

  it('continues only for PENDING_SCAN', () => {
    expect(shouldContinuePollingFileScanStatus(FileScanStatus.PENDING_SCAN)).toBe(true);
    expect(shouldContinuePollingFileScanStatus(FileScanStatus.CLEAN)).toBe(false);
    expect(shouldContinuePollingFileScanStatus(FileScanStatus.INFECTED)).toBe(false);
    expect(shouldContinuePollingFileScanStatus(FileScanStatus.SCAN_ERROR)).toBe(false);
    expect(shouldContinuePollingFileScanStatus(FileScanStatus.SCAN_UNAVAILABLE)).toBe(false);
    expect(shouldContinuePollingFileScanStatus(undefined)).toBe(false);
    expect(shouldContinuePollingFileScanStatus(null)).toBe(false);
  });
});
