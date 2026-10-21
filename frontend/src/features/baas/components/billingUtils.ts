/**
 * Shared billing utilities for BaaS components.
 */

import { BillingReportStatus } from '../../../shared/types/baas';

export function statusBadgeClass(status: string): string {
  switch (status) {
    case BillingReportStatus.DRAFT: return 'status-badge status-draft';
    case BillingReportStatus.FINALIZED: return 'status-badge status-finalized';
    case BillingReportStatus.SENT: return 'status-badge status-sent';
    case BillingReportStatus.VOID: return 'status-badge status-void';
    default: return 'status-badge';
  }
}
