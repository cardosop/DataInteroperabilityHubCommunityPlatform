/**
 * Asset Service
 * API client for asset operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Asset,
  AssetCreateRequest,
  AssetHealthScoreResponse,
  AssetListFilters,
  AssetRecommendation,
  AssetRecommendationsFilters,
  AssetUpdateRequest,
  AttachContractRequest,
  AttachDatasetRequest,
} from '../../../shared/types/assets';

const ASSETS_BASE_PATH = 'assets';

export const assetService = {
  /**
   * List assets with filtering and pagination
   */
  async list(filters: AssetListFilters = {}): Promise<PaginatedResponse<Asset>> {
    const params = new URLSearchParams();

    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.domain) params.append('domain', filters.domain);
    if (filters.status) params.append('status', filters.status);
    if (filters.visibility) params.append('visibility', filters.visibility);

    const response = await apiClient
      .getClient()
      .get<
        PaginatedResponse<Asset>
      >(`${ASSETS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`);
    return response.data;
  },

  /**
   * Get asset by ID
   */
  async getById(id: string): Promise<Asset> {
    const response = await apiClient.getClient().get<Asset>(`${ASSETS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new asset
   */
  async create(data: AssetCreateRequest): Promise<Asset> {
    const response = await apiClient.getClient().post<Asset>(`${ASSETS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Update an asset
   */
  async update(id: string, data: AssetUpdateRequest): Promise<Asset> {
    const response = await apiClient.getClient().put<Asset>(`${ASSETS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Delete an asset
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${ASSETS_BASE_PATH}/${id}/`);
  },

  /**
   * Activate an asset
   * Requires version field for optimistic locking
   */
  async activate(id: string, version: number): Promise<Asset> {
    // 60s timeout: activation may trigger semantic mapping on backend; E2E/CI load can be slow
    const response = await apiClient
      .getClient()
      .post<Asset>(`${ASSETS_BASE_PATH}/${id}/activate/`, { version }, { timeout: 60000 });
    return response.data;
  },

  /**
   * Retire an asset (ACTIVE → RETIRED lifecycle transition)
   */
  async retire(id: string, version: number): Promise<Asset> {
    const response = await apiClient
      .getClient()
      .patch<Asset>(`${ASSETS_BASE_PATH}/${id}/`, { status: 'RETIRED', version });
    return response.data;
  },

  /**
   * Attach a contract to an asset
   */
  async attachContract(id: string, data: AttachContractRequest): Promise<Asset> {
    const response = await apiClient
      .getClient()
      .post<Asset>(`${ASSETS_BASE_PATH}/${id}/contracts/`, data);
    return response.data;
  },

  /**
   * Attach a dataset to an asset
   */
  async attachDataset(id: string, data: AttachDatasetRequest): Promise<Asset> {
    const response = await apiClient
      .getClient()
      .post<Asset>(`${ASSETS_BASE_PATH}/${id}/datasets/`, data);
    return response.data;
  },

  /**
   * Create asset, dataset, and contract from uploaded file (data-first flow).
   * POST /api/v1/assets/data-first/
   */
  async createDataFirst(data: {
    file_id: string;
    key: string;
    name: string;
    description?: string;
    domain?: string;
  }): Promise<{ asset_id: string; dataset_id: string | null; contract_id: string | null }> {
    const response = await apiClient
      .getClient()
      .post<{ asset_id: string; dataset_id: string | null; contract_id: string | null }>(
        `${ASSETS_BASE_PATH}/data-first/`,
        data
      );
    return response.data;
  },

  /**
   * Get asset health score (GET /api/v1/assets/{id}/health-score/)
   */
  async getHealthScore(
    id: string,
    options?: { recalculate?: boolean; breakdown?: boolean }
  ): Promise<AssetHealthScoreResponse> {
    const params = new URLSearchParams();
    if (options?.recalculate) params.set('recalculate', 'true');
    if (options?.breakdown) params.set('breakdown', 'true');
    const qs = params.toString();
    const url = qs
      ? `${ASSETS_BASE_PATH}/${id}/health-score/?${qs}`
      : `${ASSETS_BASE_PATH}/${id}/health-score/`;
    const response = await apiClient.getClient().get<AssetHealthScoreResponse>(url);
    return response.data;
  },

  /**
   * Get asset recommendations (GET /api/v1/assets/recommendations/)
   */
  async getRecommendations(
    filters: AssetRecommendationsFilters = {}
  ): Promise<AssetRecommendation[]> {
    const params = new URLSearchParams();
    if (filters.user_id) params.set('user_id', filters.user_id);
    if (filters.asset_id) params.set('asset_id', filters.asset_id);
    if (filters.limit != null) params.set('limit', String(filters.limit));
    if (filters.include_usage_patterns !== undefined)
      params.set('include_usage_patterns', filters.include_usage_patterns ? 'true' : 'false');
    if (filters.include_lineage !== undefined)
      params.set('include_lineage', filters.include_lineage ? 'true' : 'false');
    if (filters.include_user_behavior !== undefined)
      params.set('include_user_behavior', filters.include_user_behavior ? 'true' : 'false');
    const qs = params.toString();
    const url = qs
      ? `${ASSETS_BASE_PATH}/recommendations/?${qs}`
      : `${ASSETS_BASE_PATH}/recommendations/`;
    const response = await apiClient.getClient().get<AssetRecommendation[]>(url);
    return response.data;
  },
};
