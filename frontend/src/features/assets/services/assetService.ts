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
  AssetWorkflowStatus,
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
    if (filters.dq_status) params.append('dq_status', filters.dq_status);
    if (filters.compliance_status) params.append('compliance_status', filters.compliance_status);
    if (filters.contract_id) params.append('contract_id', filters.contract_id);

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
  async update(
    id: string,
    data: AssetUpdateRequest,
    options?: { ifMatch?: string | null }
  ): Promise<Asset> {
    const headers: Record<string, string> = {};
    if (options?.ifMatch) {
      headers['If-Match'] = options.ifMatch;
    }
    const response = await apiClient
      .getClient()
      .patch<Asset>(`${ASSETS_BASE_PATH}/${id}/`, data, { headers });
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
  }): Promise<{
    asset_id: string;
    dataset_id: string | null;
    contract_id: string | null;
    /** Phase 250.6.C — surface the workflow instance id so callers
     *  (AssetCreatePage) can pass it via React Router navigation state
     *  to AssetDetailPage where the WorkflowProgressWidget polls it. */
    workflow_instance_id: string | null;
    /** Phase 250.2.B.5 — schema drift envelope for the frontend
     *  SchemaDriftBanner; null when the workflow had no contract to
     *  compare the dataset against. */
    result_summary?: {
      schema_drift?: unknown;
    };
  }> {
    const response = await apiClient
      .getClient()
      .post<{
        asset_id: string;
        dataset_id: string | null;
        contract_id: string | null;
        workflow_instance_id: string | null;
        result_summary?: { schema_drift?: unknown };
      }>(
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

  /**
   * Phase 250.6.C — get current state of an asset-creation workflow.
   *
   * GET /api/v1/assets/workflows/{workflow_instance_id}/status/
   *
   * Polled by ``useAssetWorkflowStatus`` (with F2-4 backoff) to drive
   * the ``<WorkflowProgressWidget>`` on the asset detail page during
   * the RUNNING phase. Returns 404 cross-tenant + on malformed UUID
   * (existence-leak protection — same posture as the IDOR contract).
   */
  async getAssetWorkflowStatus(
    workflowInstanceId: string
  ): Promise<AssetWorkflowStatus> {
    const response = await apiClient
      .getClient()
      .get<AssetWorkflowStatus>(
        `${ASSETS_BASE_PATH}/workflows/${workflowInstanceId}/status/`,
      );
    return response.data;
  },
};
