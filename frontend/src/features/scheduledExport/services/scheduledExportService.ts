/**
 * Scheduled Export Service
 * API client for scheduled export operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  ScheduledExport,
  ScheduledExportCreateRequest,
  ScheduledExportListFilters,
  ScheduledExportListResponse,
  ScheduledExportRun,
  ScheduledExportTriggerRequest,
  ScheduledExportTriggerResponse,
  ScheduledExportUpdateRequest,
} from '../../../shared/types/scheduledExport';

const SCHEDULED_EXPORTS_PATH = 'scheduled-exports';

export const scheduledExportService = {
  /**
   * List scheduled exports (tenant-scoped)
   */
  async list(filters: ScheduledExportListFilters = {}): Promise<ScheduledExportListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const url = qs ? `${SCHEDULED_EXPORTS_PATH}/?${qs}` : `${SCHEDULED_EXPORTS_PATH}/`;
    const response = await apiClient.getClient().get<ScheduledExportListResponse>(url);
    return response.data;
  },

  /**
   * Get scheduled export by ID
   */
  async getById(id: string): Promise<ScheduledExport> {
    const response = await apiClient
      .getClient()
      .get<ScheduledExport>(`${SCHEDULED_EXPORTS_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create scheduled export
   */
  async create(data: ScheduledExportCreateRequest): Promise<ScheduledExport> {
    const response = await apiClient
      .getClient()
      .post<ScheduledExport>(`${SCHEDULED_EXPORTS_PATH}/`, data);
    return response.data;
  },

  /**
   * Update scheduled export
   */
  async update(id: string, data: ScheduledExportUpdateRequest): Promise<ScheduledExport> {
    const response = await apiClient
      .getClient()
      .patch<ScheduledExport>(`${SCHEDULED_EXPORTS_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Delete scheduled export
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${SCHEDULED_EXPORTS_PATH}/${id}/`);
  },

  /**
   * Trigger scheduled export manually
   * Note: Increased timeout to 60s to handle slow Prefect integration service responses
   */
  async trigger(
    id: string,
    data?: ScheduledExportTriggerRequest
  ): Promise<ScheduledExportTriggerResponse> {
    const response = await apiClient.getClient().post<ScheduledExportTriggerResponse>(
      `${SCHEDULED_EXPORTS_PATH}/${id}/trigger/`,
      data || {},
      { timeout: 60000 } // 60s timeout to handle slow Prefect integration service
    );
    return response.data;
  },

  /**
   * List runs for a scheduled export
   */
  async listRuns(id: string): Promise<ScheduledExportRun[]> {
    const response = await apiClient
      .getClient()
      .get<ScheduledExportRun[]>(`${SCHEDULED_EXPORTS_PATH}/${id}/runs/`);
    return response.data;
  },

  /**
   * Get run by ID (via ScheduledExportRunViewSet)
   */
  async getRunById(runId: string): Promise<ScheduledExportRun> {
    const response = await apiClient
      .getClient()
      .get<ScheduledExportRun>(`${SCHEDULED_EXPORTS_PATH}/runs/${runId}/`);
    return response.data;
  },
};
