/**
 * Listing Service
 * API client for marketplace listing operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  ListingLineageGraph,
  ListingLineageParams,
} from '../../../shared/types/lineage';
import type {
  Listing,
  ListingCreateRequest,
  ListingUpdateRequest,
  ListingListFilters,
} from '../../../shared/types/marketplace';

const LISTINGS_BASE_PATH = 'marketplace/listings';

export const listingService = {
  /**
   * List listings with filtering and pagination
   */
  async list(filters: ListingListFilters = {}): Promise<PaginatedResponse<Listing>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.domain) params.append('domain', filters.domain);
    if (filters.pricing_model) params.append('pricing_model', filters.pricing_model);
    if (filters.status) params.append('status', filters.status);

    const queryString = params.toString();
    const url = queryString ? `${LISTINGS_BASE_PATH}/?${queryString}` : `${LISTINGS_BASE_PATH}/`;
    const response = await apiClient.getClient().get<PaginatedResponse<Listing>>(url);
    return response.data;
  },

  /**
   * Search listings
   */
  async search(query: string, filters: ListingListFilters = {}): Promise<PaginatedResponse<Listing>> {
    const params = new URLSearchParams();
    params.append('search', query);
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.domain) params.append('domain', filters.domain);
    if (filters.pricing_model) params.append('pricing_model', filters.pricing_model);
    if (filters.status) params.append('status', filters.status);

    const response = await apiClient.getClient().get<PaginatedResponse<Listing>>(
      `${LISTINGS_BASE_PATH}/search/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get listing by ID
   */
  async getById(id: string): Promise<Listing> {
    const response = await apiClient.getClient().get<Listing>(`${LISTINGS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new listing
   */
  async create(data: ListingCreateRequest): Promise<Listing> {
    const response = await apiClient.getClient().post<Listing>(`${LISTINGS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Update a listing
   */
  async update(id: string, data: ListingUpdateRequest): Promise<Listing> {
    const response = await apiClient.getClient().put<Listing>(`${LISTINGS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a listing
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${LISTINGS_BASE_PATH}/${id}/`);
  },

  /**
   * Download listing contract/document
   */
  async download(id: string): Promise<Blob> {
    const response = await apiClient.getClient().get<Blob>(`${LISTINGS_BASE_PATH}/${id}/download/`, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Preview listing contract/document
   */
  async preview(id: string, format?: string): Promise<Blob> {
    const url = format
      ? `${LISTINGS_BASE_PATH}/${id}/preview.${format}/`
      : `${LISTINGS_BASE_PATH}/${id}/preview/`;
    const response = await apiClient.getClient().get<Blob>(url, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Phase 228.F1.12 — Cross-tenant marketplace lineage.
   *
   * Fetches the lineage graph for a listing's backing asset.  The
   * `detail` parameter selects the response tier:
   *
   * - `summary` (default): pre-purchase view with transformation IP
   *   stripped on the server side (no `transformation_ref` /
   *   `job_ref` / etc.).
   * - `full`: post-purchase view; requires the consumer tenant to
   *   hold an ACTIVE Entitlement for the asset (server-enforced).
   *   A 403 with `code: ENTITLEMENT_REQUIRED` is returned otherwise.
   *
   * Returns 404 when the `lineage.cross_tenant_marketplace`
   * capability flag is OFF (intentional information-leak hardening).
   */
  async getLineage(
    id: string,
    params: ListingLineageParams = {},
  ): Promise<ListingLineageGraph> {
    const search = new URLSearchParams();
    if (params.detail) search.append('detail', params.detail);
    if (params.max_depth !== undefined) {
      search.append('max_depth', String(params.max_depth));
    }
    const qs = search.toString();
    const url = qs
      ? `${LISTINGS_BASE_PATH}/${id}/lineage/?${qs}`
      : `${LISTINGS_BASE_PATH}/${id}/lineage/`;
    const response = await apiClient.getClient().get<ListingLineageGraph>(url);
    return response.data;
  },
};
