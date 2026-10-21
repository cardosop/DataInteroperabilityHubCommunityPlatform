/**
 * Dataset Service
 * API client for dataset operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Dataset,
  DatasetCreateRequest,
  DatasetUpdateRequest,
  DatasetListFilters,
  DatasetVersion,
  DatasetVersionCompareResult,
} from '../../../shared/types/datasets';

const DATASETS_BASE_PATH = 'datasets';

export const datasetService = {
  /**
   * List datasets with filtering and pagination
   */
  async list(filters: DatasetListFilters = {}): Promise<PaginatedResponse<Dataset>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.asset_id) params.append('asset_id', filters.asset_id);
    if (filters.format) params.append('dataset_format', filters.format);
    if (filters.include_retired) params.append('include_retired', 'true');

    const response = await apiClient.getClient().get<PaginatedResponse<Dataset>>(
      `${DATASETS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get dataset by ID
   */
  async getById(id: string): Promise<Dataset> {
    const response = await apiClient.getClient().get<Dataset>(`${DATASETS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Phase 260.4.A.1 — retire a dataset (POST /datasets/{id}/retire/).
   * ACTIVE → RETIRED + retired_at; 409 DATASET_ALREADY_RETIRED when
   * already retired (idempotent on the wire).
   */
  async retire(id: string): Promise<Dataset> {
    const response = await apiClient.getClient().post<Dataset>(
      `${DATASETS_BASE_PATH}/${id}/retire/`
    );
    return response.data;
  },

  /**
   * Create a new dataset
   */
  async create(data: DatasetCreateRequest): Promise<Dataset> {
    const response = await apiClient.getClient().post<Dataset>(`${DATASETS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Update a dataset (partial update via PATCH).
   * Backend expects "asset" (UUID or null). Maps asset_id -> asset when sending.
   */
  async update(id: string, data: DatasetUpdateRequest): Promise<Dataset> {
    const payload = { ...data } as Record<string, unknown>;
    if ('asset_id' in payload) {
      if (payload.asset === undefined) payload.asset = payload.asset_id;
      delete payload.asset_id;
    }
    const response = await apiClient.getClient().patch<Dataset>(
      `${DATASETS_BASE_PATH}/${id}/`,
      payload
    );
    return response.data;
  },

  /**
   * Delete a dataset
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${DATASETS_BASE_PATH}/${id}/`);
  },

  /**
   * Get dataset versions
   */
  async getVersions(id: string): Promise<DatasetVersion[]> {
    const response = await apiClient.getClient().get<DatasetVersion[]>(
      `${DATASETS_BASE_PATH}/${id}/versions/`
    );
    return response.data;
  },

  /**
   * Compare dataset versions (schema evolution).
   *
   * GET /api/v1/datasets/{id}/versions/compare/?version1=&version2=
   * The backend (hub/apps/datasets/views.py::compare_versions) computes the
   * diff via SchemaEvolutionTracker and returns
   * `{version1, version2, compatibility_level, summary, changes}` — the
   * `changes` entries use evolution change types (FIELD_ADDED,
   * FIELD_TYPE_CHANGED, ...) rendered by DatasetVersionDiffView.
   */
  async compareVersions(
    id: string,
    version1: string,
    version2: string
  ): Promise<DatasetVersionCompareResult> {
    const params = new URLSearchParams();
    params.append('version1', version1);
    params.append('version2', version2);

    const response = await apiClient.getClient().get<DatasetVersionCompareResult>(
      `${DATASETS_BASE_PATH}/${id}/versions/compare/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get sample data rows from a dataset
   * GET /api/v1/datasets/{id}/sample/?limit=50
   */
  async getSample(id: string, limit = 50): Promise<DatasetSampleResponse> {
    const response = await apiClient.getClient().get<DatasetSampleResponse>(
      `${DATASETS_BASE_PATH}/${id}/sample/?limit=${limit}`
    );
    return response.data;
  },

  async refreshFromFile(
    datasetId: string,
    fileId: string,
  ): Promise<DatasetRefreshFromFileResponse> {
    // The backend contract is explicit: the body MUST carry the new
    // file's id (the upload IS the refresh trigger — the server
    // validates the file's tenant/status/scan before versioning).
    const response = await apiClient.getClient().post<DatasetRefreshFromFileResponse>(
      `${DATASETS_BASE_PATH}/${datasetId}/refresh-from-file/`,
      { file_id: fileId },
    );
    return response.data;
  },
};

export interface DatasetSampleResponse {
  dataset_id: string;
  format: string;
  row_count: number;
  sample_size: number;
  sample_data: Record<string, unknown>[];
}

export interface DatasetRefreshFromFileResponse {
  dataset_id: string;
  status: string;
  row_count?: number;
}

export interface DatasetSchemaDrift {
  has_contract: boolean;
  contract_id?: string | null;
  detected?: boolean;
  severity: 'NONE' | 'WARN' | 'FAIL';
  missing_fields: string[];
  extra_fields: string[];
  type_mismatches: Array<{
    field: string;
    contract_type: string;
    inferred_type: string;
    compatible?: boolean;
  }>;
  structural_incompatibility?: boolean;
  skip_reason?: string;
}
