import { describe, expect, it } from 'vitest';
import type { File } from '../../../shared/types/files';
import { FileScanStatus, FileStatus } from '../../../shared/types/files';
import { canDownloadFile } from './fileDownloadPolicy';

describe('canDownloadFile', () => {
  const base: Pick<File, 'status' | 'scan_status'> = {
    status: FileStatus.COMPLETED,
    scan_status: FileScanStatus.CLEAN,
  };

  it('allows ACTIVE or COMPLETED when scan is not pending or infected', () => {
    expect(canDownloadFile({ ...base, status: FileStatus.ACTIVE, scan_status: FileScanStatus.CLEAN })).toBe(
      true
    );
    expect(
      canDownloadFile({ ...base, status: FileStatus.COMPLETED, scan_status: FileScanStatus.SCAN_UNAVAILABLE })
    ).toBe(true);
    expect(canDownloadFile({ ...base, status: FileStatus.COMPLETED, scan_status: FileScanStatus.SCAN_ERROR })).toBe(
      true
    );
  });

  it('blocks non-terminal lifecycle statuses', () => {
    expect(canDownloadFile({ ...base, status: FileStatus.PENDING })).toBe(false);
    expect(canDownloadFile({ ...base, status: FileStatus.UPLOADING })).toBe(false);
    expect(canDownloadFile({ ...base, status: FileStatus.DELETED })).toBe(false);
  });

  it('blocks PENDING_SCAN and INFECTED', () => {
    expect(canDownloadFile({ ...base, scan_status: FileScanStatus.PENDING_SCAN })).toBe(false);
    expect(canDownloadFile({ ...base, scan_status: FileScanStatus.INFECTED })).toBe(false);
  });

  it('treats missing scan_status as pending scan', () => {
    expect(canDownloadFile({ status: FileStatus.COMPLETED })).toBe(false);
  });
});
