/**
 * Audit Service
 * API client for audit event operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  AuditEvent,
  AuditEventExportFormat,
  AuditEventListFilters,
  AuditEventListResponse,
  AuditEventRetentionPolicy,
  AuditEventRetentionPolicyInput,
  ResourceActivityResponse,
  ResourceType,
} from '../../../shared/types/audit';
import type { PaginatedResponse } from '../../../shared/types/api';

const AUDIT_EVENTS_PATH = 'audit/audit-events';

export const auditService = {
  /**
   * List audit events (tenant-scoped)
   */
  async list(filters: AuditEventListFilters = {}): Promise<AuditEventListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    if (filters.resource_type) params.set('resource_type', filters.resource_type);
    if (filters.action) params.set('action', filters.action);
    if (filters.actor_user_id) params.set('actor_user_id', filters.actor_user_id);
    if (filters.start_date) params.set('start_date', filters.start_date);
    if (filters.end_date) params.set('end_date', filters.end_date);
    const qs = params.toString();
    const url = qs ? `${AUDIT_EVENTS_PATH}/?${qs}` : `${AUDIT_EVENTS_PATH}/`;
    const response = await apiClient.getClient().get<AuditEventListResponse>(url);
    return response.data;
  },

  /**
   * Get audit event by ID
   */
  async getById(id: string): Promise<AuditEvent> {
    const response = await apiClient.getClient().get<AuditEvent>(`${AUDIT_EVENTS_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Export audit events (CSV or JSON)
   * Returns blob URL for download
   */
  async export(
    format: AuditEventExportFormat,
    filters: Omit<AuditEventListFilters, 'page' | 'page_size'> = {}
  ): Promise<Blob> {
    const params = new URLSearchParams();
    params.set('format', format);
    if (filters.resource_type) params.set('resource_type', filters.resource_type);
    if (filters.action) params.set('action', filters.action);
    if (filters.actor_user_id) params.set('actor_user_id', filters.actor_user_id);
    if (filters.start_date) params.set('start_date', filters.start_date);
    if (filters.end_date) params.set('end_date', filters.end_date);
    const url = `${AUDIT_EVENTS_PATH}/export/?${params.toString()}`;

    const response = await apiClient.getClient().get<Blob>(url, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Phase 224.3 — fetch the sanitized activity feed for a single resource.
   * Available to any authenticated tenant member (server scopes by tenant).
   */
  async resourceActivity(
    resourceType: ResourceType,
    resourceId: string,
  ): Promise<ResourceActivityResponse> {
    const params = new URLSearchParams();
    params.set('resource_type', resourceType);
    params.set('resource_id', resourceId);
    const url = `${AUDIT_EVENTS_PATH}/resource-activity/?${params.toString()}`;
    const response = await apiClient.getClient().get<ResourceActivityResponse>(url);
    return response.data;
  },

  // ── Phase 234.5 — Audit Event Retention Policies ──────────────────────

  /**
   * List audit event retention policies for the current tenant.
   */
  async listRetentionPolicies(): Promise<PaginatedResponse<AuditEventRetentionPolicy>> {
    const url = `${AUDIT_EVENTS_PATH}/retention-policies/`;
    const response = await apiClient.getClient().get<PaginatedResponse<AuditEventRetentionPolicy>>(url);
    return response.data;
  },

  /**
   * Create an audit event retention policy override.
   */
  async createRetentionPolicy(input: AuditEventRetentionPolicyInput): Promise<AuditEventRetentionPolicy> {
    const url = `${AUDIT_EVENTS_PATH}/retention-policies/`;
    const response = await apiClient.getClient().post<AuditEventRetentionPolicy>(url, input);
    return response.data;
  },

  /**
   * Update (partial) an audit event retention policy override.
   */
  async updateRetentionPolicy(
    id: string,
    input: Partial<AuditEventRetentionPolicyInput> & { enabled?: boolean },
  ): Promise<AuditEventRetentionPolicy> {
    const url = `${AUDIT_EVENTS_PATH}/retention-policies/${id}/`;
    const response = await apiClient.getClient().patch<AuditEventRetentionPolicy>(url, input);
    return response.data;
  },

  /**
   * Delete an audit event retention policy override.
   */
  async deleteRetentionPolicy(id: string): Promise<void> {
    const url = `${AUDIT_EVENTS_PATH}/retention-policies/${id}/`;
    await apiClient.getClient().delete(url);
  },
};
