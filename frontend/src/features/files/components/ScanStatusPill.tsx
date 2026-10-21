/**
 * Malware scan status pill (Phase 260.2.C / D260.7).
 * One visual variant per backend FileScanStatus value.
 */

import type { FileScanStatus } from '../../../shared/types/files';
import styles from './ScanStatusPill.module.css';

export type ScanStatusPillProps = {
  status: FileScanStatus | string;
  scannedAt?: string | null;
  /** Unique id for tables with multiple rows (defaults to `scan-status-pill`). */
  testId?: string;
};

const LABELS: Record<string, string> = {
  PENDING_SCAN: 'Pending scan',
  CLEAN: 'Clean',
  INFECTED: 'Infected',
  SCAN_UNAVAILABLE: 'Scan unavailable',
  SCAN_ERROR: 'Scan error',
};

function variantClass(status: string): string {
  switch (status) {
    case 'PENDING_SCAN':
      return styles.pillPending;
    case 'CLEAN':
      return styles.pillClean;
    case 'INFECTED':
      return styles.pillInfected;
    case 'SCAN_UNAVAILABLE':
      return styles.pillUnavailable;
    case 'SCAN_ERROR':
      return styles.pillError;
    default:
      return styles.pillUnknown;
  }
}

export function ScanStatusPill({ status, scannedAt, testId = 'scan-status-pill' }: ScanStatusPillProps) {
  const label = LABELS[status] ?? status;
  const title =
    scannedAt != null && scannedAt !== ''
      ? `Last scan: ${new Date(scannedAt).toLocaleString()}`
      : undefined;
  const ariaLabel = title ? `${label}. ${title}` : `${label}. Malware scan status.`;

  return (
    <span
      className={`${styles.pill} ${variantClass(status)}`}
      data-testid={testId}
      data-scan-status={status}
      title={title}
      role="status"
      aria-label={ariaLabel}
    >
      {label}
    </span>
  );
}
