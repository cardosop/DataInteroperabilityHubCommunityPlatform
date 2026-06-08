/**
 * Audit Event Types
 * Aligned with backend AuditEventSerializer and AuditEventViewSet
 */

export type AuditEventResult = 'SUCCESS' | 'FAILURE' | 'WARNING';

export interface AuditEvent {
  id: string;
  tenant: string;
  tenant_name: string;
  actor_user: string | null;
  actor_user_email: string | null;
  resource_type: string;
  resource_id: string | null;
  action: string;
  result: AuditEventResult;
  details_json: Record<string, unknown>;
  timestamp: string;
}

export interface AuditEventListFilters {
  page?: number;
  page_size?: number;
  resource_type?: string;
  action?: string;
  actor_user_id?: string;
  start_date?: string; // ISO 8601 format
  end_date?: string; // ISO 8601 format
}

export interface AuditEventListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: AuditEvent[];
}

export type AuditEventExportFormat = 'csv' | 'json';

/**
 * Phase 224.3 — sanitized per-resource activity feed shape.
 * Raw ``details_json`` is scrubbed server-side (``sanitize_activity_details``);
 * clients should treat ``details`` as a safe, display-only bag of strings.
 */
export interface ResourceActivityEvent {
  id: string;
  action: string;
  result: AuditEventResult;
  timestamp: string;
  resource_type: string;
  resource_id: string | null;
  actor_display_name: string;
  details: Record<string, unknown>;
}

export interface ResourceActivityResponse {
  results: ResourceActivityEvent[];
}

export type ResourceType = 'ASSET' | 'CONTRACT' | 'ORDER' | 'ACCESS_REQUEST' | string;

export interface AuditEventRetentionPolicy {
  id: string;
  event_type: string;
  retention_days: number;
  enabled?: boolean;
  regulation_keys: string[];
  created_at: string;
  updated_at: string;
}

export interface AuditEventRetentionPolicyInput {
  event_type: string;
  retention_days?: number;
  regulation_keys?: string[];
}
