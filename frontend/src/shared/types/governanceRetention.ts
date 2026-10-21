/**
 * Governance Retention Policy Types
 * Aligned with backend RetentionPolicySerializer and retention_views
 */

export const RetentionPolicyType = {
  TIME_BASED: 'TIME_BASED',
  EVENT_BASED: 'EVENT_BASED',
} as const;
export type RetentionPolicyType = (typeof RetentionPolicyType)[keyof typeof RetentionPolicyType];

export const RetentionAction = {
  SOFT_DELETE: 'SOFT_DELETE',
  HARD_DELETE: 'HARD_DELETE',
  ARCHIVE: 'ARCHIVE',
} as const;
export type RetentionAction = (typeof RetentionAction)[keyof typeof RetentionAction];

export interface RetentionPolicy {
  id: string;
  tenant: string;
  name: string;
  description: string | null;
  asset: string | null;
  dataset: string | null;
  file: string | null;
  policy_type: RetentionPolicyType;
  retention_period_days: number | null;
  event_trigger: string | null;
  action: RetentionAction;
  grace_period_days: number;
  legal_hold: boolean;
  legal_hold_reason: string | null;
  legal_hold_expires_at: string | null;
  enabled: boolean;
  last_enforced_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface RetentionPolicyCreateRequest {
  name: string;
  description?: string;
  asset_id?: string;
  dataset_id?: string;
  file_id?: string;
  policy_type: RetentionPolicyType;
  retention_period_days?: number;
  event_trigger?: string;
  action?: RetentionAction;
  grace_period_days?: number;
  legal_hold?: boolean;
  legal_hold_reason?: string;
  legal_hold_expires_at?: string;
  enabled?: boolean;
}

export interface RetentionPolicyUpdateRequest extends Partial<RetentionPolicyCreateRequest> {
  id: string;
}

export interface RetentionPolicyListFilters {
  page?: number;
  page_size?: number;
  asset_id?: string;
  dataset_id?: string;
  file_id?: string;
  enabled?: boolean;
}
