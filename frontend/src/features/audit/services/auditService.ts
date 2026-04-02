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
} from '../../../shared/types/audit';

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
};
