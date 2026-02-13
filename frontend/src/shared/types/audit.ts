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
