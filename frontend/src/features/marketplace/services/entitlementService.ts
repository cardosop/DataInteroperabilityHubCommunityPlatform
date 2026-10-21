/**
 * Entitlement Service
 * API client for marketplace entitlement operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Entitlement,
  EntitlementListFilters,
  CheckAccessRequest,
  CheckAccessResponse,
} from '../../../shared/types/marketplace';

const ENTITLEMENTS_BASE_PATH = 'marketplace/entitlements';

export const entitlementService = {
  /**
   * List entitlements with filtering and pagination
   */
  async list(filters: EntitlementListFilters = {}): Promise<PaginatedResponse<Entitlement>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.status) params.append('status', filters.status);
    if (filters.listing_id) params.append('listing_id', filters.listing_id);
    if (filters.asset_id) params.append('asset_id', filters.asset_id);

    const response = await apiClient.getClient().get<PaginatedResponse<Entitlement>>(
      `${ENTITLEMENTS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get entitlement by ID
   */
  async getById(id: string): Promise<Entitlement> {
    const response = await apiClient.getClient().get<Entitlement>(`${ENTITLEMENTS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Check access to an asset
   */
  async checkAccess(data: CheckAccessRequest): Promise<CheckAccessResponse> {
    const response = await apiClient.getClient().post<CheckAccessResponse>(
      `${ENTITLEMENTS_BASE_PATH}/check-access/`,
      data
    );
    return response.data;
  },

  /**
   * Revoke an entitlement
   */
  async revoke(id: string): Promise<Entitlement> {
    const response = await apiClient.getClient().post<Entitlement>(`${ENTITLEMENTS_BASE_PATH}/${id}/revoke/`);
    return response.data;
  },
};
