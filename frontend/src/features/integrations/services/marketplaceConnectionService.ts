/**
 * Marketplace Connection Service
 * API client for marketplace connection operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  MarketplaceConnection,
  MarketplaceConnectionCreate,
  MarketplaceConnectionUpdate,
  MarketplaceConnectionListFilters,
  MarketplaceConnectionTestResponse,
} from '../../../shared/types/integrations';

const CONNECTIONS_BASE_PATH = 'integrations/marketplace/connections';

export const marketplaceConnectionService = {
  /**
   * List connections with filtering and pagination
   */
  async list(filters: MarketplaceConnectionListFilters = {}): Promise<PaginatedResponse<MarketplaceConnection>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.marketplace_type) params.append('marketplace_type', filters.marketplace_type);
    if (filters.is_active !== undefined) params.append('is_active', filters.is_active.toString());
    if (filters.search) params.append('search', filters.search);

    const response = await apiClient.getClient().get<PaginatedResponse<MarketplaceConnection>>(
      `${CONNECTIONS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    const data = response.data;
    if (data == null) {
      return {
        results: [],
        count: 0,
        page: 1,
        page_size: 50,
        total_pages: 0,
        has_next: false,
        has_previous: false,
        next_page: null,
        previous_page: null,
      };
    }
    return data;
  },

  /**
   * Get connection by ID
   */
  async getById(id: string): Promise<MarketplaceConnection> {
    const response = await apiClient.getClient().get<MarketplaceConnection>(`${CONNECTIONS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new connection
   */
  async create(data: MarketplaceConnectionCreate): Promise<MarketplaceConnection> {
    const response = await apiClient.getClient().post<MarketplaceConnection>(`${CONNECTIONS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Update a connection
   */
  async update(id: string, data: MarketplaceConnectionUpdate): Promise<MarketplaceConnection> {
    const response = await apiClient.getClient().put<MarketplaceConnection>(`${CONNECTIONS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Partially update a connection
   */
  async partialUpdate(id: string, data: Partial<MarketplaceConnectionUpdate>): Promise<MarketplaceConnection> {
    const response = await apiClient.getClient().patch<MarketplaceConnection>(`${CONNECTIONS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a connection
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${CONNECTIONS_BASE_PATH}/${id}/`);
  },

  /**
   * Test a connection
   */
  async test(id: string): Promise<MarketplaceConnectionTestResponse> {
    const response = await apiClient.getClient().post<MarketplaceConnectionTestResponse>(
      `${CONNECTIONS_BASE_PATH}/${id}/test/`
    );
    return response.data;
  },
};
