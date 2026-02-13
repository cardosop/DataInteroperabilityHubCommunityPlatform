/**
 * Data Quality Service
 * API client for DQ run operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  DQRun,
  DQRunCreateRequest,
  DQRunListFilters,
  DQRunResults,
} from '../../../shared/types/dq';

const DQ_BASE_PATH = 'dq/runs';

export const dqService = {
  /**
   * List DQ runs with filtering and pagination
   */
  async list(filters: DQRunListFilters = {}): Promise<PaginatedResponse<DQRun>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.status) params.append('status', filters.status);
    if (filters.dataset_id) params.append('dataset_id', filters.dataset_id);
    if (filters.date_from) params.append('date_from', filters.date_from);
    if (filters.date_to) params.append('date_to', filters.date_to);

    const response = await apiClient.getClient().get<PaginatedResponse<DQRun>>(
      `${DQ_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get DQ run by ID
   */
  async getById(id: string): Promise<DQRun> {
    const response = await apiClient.getClient().get<DQRun>(`${DQ_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new DQ run
   */
  async create(data: DQRunCreateRequest): Promise<DQRun> {
    const response = await apiClient.getClient().post<DQRun>(`${DQ_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Get DQ run results
   */
  async getResults(id: string): Promise<DQRunResults> {
    const response = await apiClient.getClient().get<DQRunResults>(
      `${DQ_BASE_PATH}/${id}/results/`
    );
    return response.data;
  },
};
