/**
 * Governance (Access Requests) Types
 * Aligned with backend AccessRequestSerializer and access_request_views
 */

export const AccessRequestStatus = {
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  EXPIRED: 'EXPIRED',
  REVOKED: 'REVOKED',
} as const;
export type AccessRequestStatus = (typeof AccessRequestStatus)[keyof typeof AccessRequestStatus];

export interface AccessRequest {
  id: string;
  tenant: string;
  requested_by: string;
  asset: string | null;
  dataset: string | null;
  file: string | null;
  reason: string;
  requested_access_type: string;
  status: AccessRequestStatus;
  requires_approval: boolean;
  approval_workflow: unknown[] | null;
  current_approval_step: number;
  approvers: string[] | null;
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  expires_at: string | null;
  access_granted_at: string | null;
  order: string | null;
  created_at: string;
  updated_at: string;
}

export interface AccessRequestCreateRequest {
  reason: string;
  asset_id?: string;
  dataset_id?: string;
  file_id?: string;
  requested_access_type?: string;
  expires_at?: string;
}

export interface AccessRequestListFilters {
  page?: number;
  page_size?: number;
  status?: AccessRequestStatus;
  asset_id?: string;
  dataset_id?: string;
}

/** Phase 272.1 — comment on an access request. */
export interface AccessRequestComment {
  id: string;
  access_request: string;
  author: string | null;
  author_email: string | null;
  body: string;
  created_at: string;
  updated_at: string;
}
