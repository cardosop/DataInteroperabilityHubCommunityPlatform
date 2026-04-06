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
   * Compare dataset versions
   */
  async compareVersions(id: string, version1: string, version2: string): Promise<{
    version1: DatasetVersion;
    version2: DatasetVersion;
    differences: Array<{
      field: string;
      version1_value: unknown;
      version2_value: unknown;
    }>;
  }> {
    const params = new URLSearchParams();
    params.append('version1', version1);
    params.append('version2', version2);

    const response = await apiClient.getClient().get<{
      version1: DatasetVersion;
      version2: DatasetVersion;
      differences: Array<{ field: string; version1_value: unknown; version2_value: unknown }>;
    }>(
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
};

export interface DatasetSampleResponse {
  dataset_id: string;
  format: string;
  row_count: number;
  sample_size: number;
  sample_data: Record<string, unknown>[];
}
