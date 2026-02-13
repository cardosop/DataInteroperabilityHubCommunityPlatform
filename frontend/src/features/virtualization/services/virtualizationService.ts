/**
 * Virtualization Service
 * API client for virtual dataset and query execution operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  VirtualDataset,
  VirtualDatasetCreateRequest,
  VirtualDatasetUpdateRequest,
  VirtualDatasetListFilters,
  VirtualDatasetValidationResponse,
  VirtualDatasetVersion,
  QueryExecution,
  QueryExecutionCreateRequest,
  QueryExecutionListFilters,
  QueryExecutionResult,
  QueryExecutionProgress,
  QueryExecutionCancelResponse,
} from '../../../shared/types/virtualization';

const VIRTUALIZATION_BASE_PATH = 'virtualization';

export const virtualizationService = {
  /**
   * List virtual datasets with filtering and pagination
   */
  async listDatasets(filters: VirtualDatasetListFilters = {}): Promise<PaginatedResponse<VirtualDataset>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.status) params.append('status', filters.status);
    if (filters.query_type) params.append('query_type', filters.query_type);
    if (filters.owner) params.append('owner', filters.owner);
    if (filters.created_by) params.append('created_by', filters.created_by);

    const response = await apiClient.getClient().get<PaginatedResponse<VirtualDataset>>(
      `${VIRTUALIZATION_BASE_PATH}/datasets/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get virtual dataset by ID
   */
  async getDatasetById(id: string): Promise<VirtualDataset> {
    const response = await apiClient.getClient().get<VirtualDataset>(`${VIRTUALIZATION_BASE_PATH}/datasets/${id}/`);
    return response.data;
  },

  /**
   * Create a new virtual dataset
   */
  async createDataset(data: VirtualDatasetCreateRequest): Promise<VirtualDataset> {
    const response = await apiClient.getClient().post<VirtualDataset>(`${VIRTUALIZATION_BASE_PATH}/datasets/`, data);
    return response.data;
  },

  /**
   * Update a virtual dataset
   */
  async updateDataset(id: string, data: VirtualDatasetUpdateRequest): Promise<VirtualDataset> {
    const response = await apiClient.getClient().put<VirtualDataset>(`${VIRTUALIZATION_BASE_PATH}/datasets/${id}/`, data);
    return response.data;
  },

  /**
   * Partially update a virtual dataset
   */
  async patchDataset(id: string, data: Partial<VirtualDatasetUpdateRequest>): Promise<VirtualDataset> {
    const response = await apiClient.getClient().patch<VirtualDataset>(`${VIRTUALIZATION_BASE_PATH}/datasets/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a virtual dataset
   */
  async deleteDataset(id: string): Promise<void> {
    await apiClient.getClient().delete(`${VIRTUALIZATION_BASE_PATH}/datasets/${id}/`);
  },

  /**
   * Validate a virtual dataset
   */
  async validateDataset(id: string): Promise<VirtualDatasetValidationResponse> {
    const response = await apiClient.getClient().post<VirtualDatasetValidationResponse>(
      `${VIRTUALIZATION_BASE_PATH}/datasets/${id}/validate/`,
      {}
    );
    return response.data;
  },

  /**
   * Get dataset versions
   */
  async getDatasetVersions(id: string): Promise<VirtualDatasetVersion[]> {
    const response = await apiClient.getClient().get<VirtualDatasetVersion[]>(
      `${VIRTUALIZATION_BASE_PATH}/datasets/${id}/versions/`
    );
    return response.data;
  },

  /**
   * Execute a query on a virtual dataset
   */
  async executeQuery(datasetId: string, data: QueryExecutionCreateRequest): Promise<QueryExecution> {
    const response = await apiClient.getClient().post<QueryExecution>(
      `${VIRTUALIZATION_BASE_PATH}/datasets/${datasetId}/queries/`,
      data
    );
    return response.data;
  },

  /**
   * List query executions with filtering and pagination
   */
  async listQueryExecutions(filters: QueryExecutionListFilters = {}): Promise<PaginatedResponse<QueryExecution>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.status) params.append('status', filters.status);
    if (filters.virtual_dataset) params.append('virtual_dataset', filters.virtual_dataset);

    const response = await apiClient.getClient().get<PaginatedResponse<QueryExecution>>(
      `${VIRTUALIZATION_BASE_PATH}/queries/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get query execution by ID
   */
  async getQueryExecutionById(id: string): Promise<QueryExecution> {
    const response = await apiClient.getClient().get<QueryExecution>(`${VIRTUALIZATION_BASE_PATH}/queries/${id}/`);
    return response.data;
  },

  /**
   * Cancel a query execution
   */
  async cancelQueryExecution(id: string): Promise<QueryExecutionCancelResponse> {
    const response = await apiClient.getClient().post<QueryExecutionCancelResponse>(
      `${VIRTUALIZATION_BASE_PATH}/queries/${id}/cancel/`,
      {}
    );
    return response.data;
  },

  /**
   * Get query execution progress
   */
  async getQueryExecutionProgress(id: string): Promise<QueryExecutionProgress> {
    const response = await apiClient.getClient().get<QueryExecutionProgress>(
      `${VIRTUALIZATION_BASE_PATH}/queries/${id}/progress/`
    );
    return response.data;
  },

  /**
   * Get query execution result
   */
  async getQueryExecutionResult(
    id: string,
    page?: number,
    pageSize?: number,
    format: 'json' | 'csv' | 'parquet' = 'json'
  ): Promise<QueryExecutionResult> {
    const params = new URLSearchParams();
    if (page) params.append('page', page.toString());
    if (pageSize) params.append('page_size', pageSize.toString());
    params.append('format', format);

    const response = await apiClient.getClient().get<QueryExecutionResult>(
      `${VIRTUALIZATION_BASE_PATH}/queries/${id}/result/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Stream query execution result (for large results)
   */
  async streamQueryExecutionResult(id: string, format: 'json' | 'csv' | 'parquet' = 'json'): Promise<Blob> {
    const params = new URLSearchParams();
    params.append('format', format);

    const response = await apiClient.getClient().get<Blob>(
      `${VIRTUALIZATION_BASE_PATH}/queries/${id}/stream/${params.toString() ? `?${params.toString()}` : ''}`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },
};
