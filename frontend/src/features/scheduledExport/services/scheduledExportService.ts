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
   *
   * The backend returns 207 ``{resource, deployment_sync}`` when the
   * Prefect deployment sync fails (the resource itself was created) —
   * unwrap that envelope so callers always get the ScheduledExport and
   * the create page never navigates to ``/scheduled-exports/undefined``.
   */
  async create(data: ScheduledExportCreateRequest): Promise<ScheduledExport> {
    const response = await apiClient.getClient().post<
      ScheduledExport & { resource?: ScheduledExport }
    >(`${SCHEDULED_EXPORTS_PATH}/`, data);
    return response.data.resource ?? response.data;
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
   *
   * The dlt dispatch branch executes the whole export SYNCHRONOUSLY
   * inside this request (tenant.data_movement_enabled → services.py
   * execute_export) — a cold dlt run in the API container can exceed
   * the client's default 30s and abort the UI request while the run
   * completes server-side. 120s covers the cold path.
   */
  async trigger(
    id: string,
    data?: ScheduledExportTriggerRequest
  ): Promise<ScheduledExportTriggerResponse> {
    const response = await apiClient.getClient().post<ScheduledExportTriggerResponse>(
      `${SCHEDULED_EXPORTS_PATH}/${id}/trigger/`,
      data || {},
      { timeout: 120000 }
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
