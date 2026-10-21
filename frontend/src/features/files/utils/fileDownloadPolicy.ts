/**
 * Mirrors backend ``File.can_download()`` — lifecycle ACTIVE/COMPLETED and malware gates.
 */

import { FileScanStatus, FileStatus, type File } from '../../../shared/types/files';

export function canDownloadFile(file: Pick<File, 'status' | 'scan_status'>): boolean {
  const st = file.status;
  if (st !== FileStatus.ACTIVE && st !== FileStatus.COMPLETED) return false;
  const scan = file.scan_status ?? FileScanStatus.PENDING_SCAN;
  return scan !== FileScanStatus.PENDING_SCAN && scan !== FileScanStatus.INFECTED;
}
