/**
 * Marketplace Sync Job Service
 * API client for marketplace sync job operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  MarketplaceSyncJob,
  MarketplaceSyncJobCreate,
  MarketplaceSyncJobCancel,
  MarketplaceSyncJobListFilters,
} from '../../../shared/types/integrations';

const SYNC_JOBS_BASE_PATH = 'integrations/marketplace/sync';

export const marketplaceSyncJobService = {
  /**
   * List sync jobs with filtering and pagination
   */
  async list(filters: MarketplaceSyncJobListFilters = {}): Promise<PaginatedResponse<MarketplaceSyncJob>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.connection_id) params.append('connection_id', filters.connection_id);
    if (filters.direction) params.append('direction', filters.direction);
    if (filters.status) params.append('status', filters.status);

    const response = await apiClient.getClient().get<PaginatedResponse<MarketplaceSyncJob>>(
      `${SYNC_JOBS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get sync job by ID
   */
  async getById(id: string): Promise<MarketplaceSyncJob> {
    const response = await apiClient.getClient().get<MarketplaceSyncJob>(`${SYNC_JOBS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new sync job
   */
  async create(data: MarketplaceSyncJobCreate): Promise<MarketplaceSyncJob> {
    const response = await apiClient.getClient().post<MarketplaceSyncJob>(`${SYNC_JOBS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Cancel a sync job
   */
  async cancel(id: string, data?: MarketplaceSyncJobCancel): Promise<MarketplaceSyncJob> {
    const response = await apiClient.getClient().post<MarketplaceSyncJob>(
      `${SYNC_JOBS_BASE_PATH}/${id}/cancel/`,
      data || {}
    );
    return response.data;
  },
};
