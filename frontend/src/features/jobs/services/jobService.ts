/**
 * Job Service
 * API client for job operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Job,
  JobCreateRequest,
  JobListFilters,
} from '../../../shared/types/jobs';

const JOBS_BASE_PATH = 'jobs';

export const jobService = {
  /**
   * List jobs with filtering and pagination
   */
  async list(filters: JobListFilters = {}): Promise<PaginatedResponse<Job>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.type) params.append('type', filters.type);
    if (filters.status) params.append('status', filters.status);
    if (filters.resource_type) params.append('resource_type', filters.resource_type);
    if (filters.resource_id) params.append('resource_id', filters.resource_id);

    const response = await apiClient.getClient().get<PaginatedResponse<Job>>(
      `${JOBS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get job by ID
   */
  async getById(id: string): Promise<Job> {
    const response = await apiClient.getClient().get<Job>(`${JOBS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new job
   */
  async create(data: JobCreateRequest): Promise<Job> {
    const response = await apiClient.getClient().post<Job>(`${JOBS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Cancel a job
   */
  async cancel(id: string): Promise<Job> {
    const response = await apiClient.getClient().post<Job>(`${JOBS_BASE_PATH}/${id}/cancel/`);
    return response.data;
  },
};
