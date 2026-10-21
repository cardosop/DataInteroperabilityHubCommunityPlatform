/**
 * Marketplace Mapping Service
 * API client for marketplace mapping operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  MarketplaceMapping,
  MarketplaceMappingListFilters,
} from '../../../shared/types/integrations';

const MAPPINGS_BASE_PATH = 'integrations/marketplace/mappings';

export const marketplaceMappingService = {
  /**
   * List mappings with filtering and pagination
   */
  async list(filters: MarketplaceMappingListFilters = {}): Promise<PaginatedResponse<MarketplaceMapping>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.connection_id) params.append('connection_id', filters.connection_id);
    if (filters.hub_asset_id) params.append('hub_asset_id', filters.hub_asset_id);
    if (filters.external_listing_id) params.append('external_listing_id', filters.external_listing_id);

    const response = await apiClient.getClient().get<PaginatedResponse<MarketplaceMapping>>(
      `${MAPPINGS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get mapping by ID
   */
  async getById(id: string): Promise<MarketplaceMapping> {
    const response = await apiClient.getClient().get<MarketplaceMapping>(`${MAPPINGS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Delete a mapping
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${MAPPINGS_BASE_PATH}/${id}/`);
  },
};
