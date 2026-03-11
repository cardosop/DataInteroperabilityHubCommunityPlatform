/**
 * Scheduled Ingestion Service
 * API client for scheduled ingestion operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  ScheduledIngestion,
  ScheduledIngestionListFilters,
  ScheduledIngestionListResponse,
  ScheduledIngestionCreateRequest,
  ScheduledIngestionUpdateRequest,
  ScheduledIngestionTriggerRequest,
  ScheduledIngestionTriggerResponse,
  ScheduledIngestionRun,
} from '../../../shared/types/scheduledIngestion';

const SCHEDULED_INGESTIONS_PATH = 'scheduled-ingestions';

export const scheduledIngestionService = {
  /**
   * List scheduled ingestions (tenant-scoped)
   */
  async list(filters: ScheduledIngestionListFilters = {}): Promise<ScheduledIngestionListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const url = qs ? `${SCHEDULED_INGESTIONS_PATH}/?${qs}` : `${SCHEDULED_INGESTIONS_PATH}/`;
    const response = await apiClient.getClient().get<ScheduledIngestionListResponse>(url);
    const data = response.data;
    if (data == null) {
      return { results: [], count: 0, next: null, previous: null };
    }
    return data;
  },

  /**
   * Get scheduled ingestion by ID
   */
  async getById(id: string): Promise<ScheduledIngestion> {
    const response = await apiClient
      .getClient()
      .get<ScheduledIngestion>(`${SCHEDULED_INGESTIONS_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create scheduled ingestion
   */
  async create(data: ScheduledIngestionCreateRequest): Promise<ScheduledIngestion> {
    const response = await apiClient
      .getClient()
      .post<ScheduledIngestion>(`${SCHEDULED_INGESTIONS_PATH}/`, data);
    return response.data;
  },

  /**
   * Update scheduled ingestion
   */
  async update(id: string, data: ScheduledIngestionUpdateRequest): Promise<ScheduledIngestion> {
    const response = await apiClient
      .getClient()
      .patch<ScheduledIngestion>(`${SCHEDULED_INGESTIONS_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Delete scheduled ingestion
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${SCHEDULED_INGESTIONS_PATH}/${id}/`);
  },

  /**
   * Trigger scheduled ingestion manually
   * Note: Increased timeout to 60s to handle slow Prefect integration service responses
   */
  async trigger(id: string, data?: ScheduledIngestionTriggerRequest): Promise<ScheduledIngestionTriggerResponse> {
    const response = await apiClient
      .getClient()
      .post<ScheduledIngestionTriggerResponse>(
        `${SCHEDULED_INGESTIONS_PATH}/${id}/trigger/`,
        data || {},
        { timeout: 60000 } // 60s timeout to handle slow Prefect integration service
      );
    return response.data;
  },

  /**
   * List runs for a scheduled ingestion
   */
  async listRuns(id: string): Promise<ScheduledIngestionRun[]> {
    const response = await apiClient
      .getClient()
      .get<ScheduledIngestionRun[]>(`${SCHEDULED_INGESTIONS_PATH}/${id}/runs/`);
    return response.data;
  },

  /**
   * Get run by ID (via ScheduledIngestionRunViewSet)
   */
  async getRunById(runId: string): Promise<ScheduledIngestionRun> {
    const response = await apiClient
      .getClient()
      .get<ScheduledIngestionRun>(`${SCHEDULED_INGESTIONS_PATH}/runs/${runId}/`);
    return response.data;
  },
};
