/**
 * Transformation Pipeline Service — Phase 115D.1
 * API client for transformation pipeline and execution operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  PipelineExecution,
  TransformationListFilters,
  TransformationPipeline,
  TransformationPipelineCreateRequest,
  TransformationPipelineUpdateRequest,
  PipelineExecuteRequest,
} from '../../../shared/types/transformation';

interface PaginatedResponse<T> {
  results: T[];
  count: number;
}

const PIPELINES_BASE = 'transformation/pipelines';
const EXECUTIONS_BASE = 'transformation/executions';

export const transformationService = {
  async list(
    filters: TransformationListFilters = {},
  ): Promise<PaginatedResponse<TransformationPipeline>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', String(filters.page));
    if (filters.page_size) params.append('page_size', String(filters.page_size));
    if (filters.status) params.append('status', filters.status);
    if (filters.search) params.append('search', filters.search);
    if (filters.ordering) params.append('ordering', filters.ordering);
    const url = params.toString()
      ? `${PIPELINES_BASE}/?${params}`
      : `${PIPELINES_BASE}/`;
    const resp = await apiClient.getClient().get<PaginatedResponse<TransformationPipeline>>(url);
    return resp.data;
  },

  async getById(id: string): Promise<TransformationPipeline> {
    const resp = await apiClient.getClient().get<TransformationPipeline>(
      `${PIPELINES_BASE}/${id}/`,
    );
    return resp.data;
  },

  async create(data: TransformationPipelineCreateRequest): Promise<TransformationPipeline> {
    const resp = await apiClient.getClient().post<TransformationPipeline>(
      `${PIPELINES_BASE}/`, data,
    );
    return resp.data;
  },

  async update(
    id: string, data: TransformationPipelineUpdateRequest,
  ): Promise<TransformationPipeline> {
    const resp = await apiClient.getClient().patch<TransformationPipeline>(
      `${PIPELINES_BASE}/${id}/`, data,
    );
    return resp.data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.getClient().delete(`${PIPELINES_BASE}/${id}/`);
  },

  async execute(
    id: string, data: PipelineExecuteRequest,
  ): Promise<PipelineExecution> {
    const resp = await apiClient.getClient().post<PipelineExecution>(
      `${PIPELINES_BASE}/${id}/execute/`, data,
    );
    return resp.data;
  },

  async validate(id: string): Promise<{ valid: boolean; errors: string[] }> {
    const resp = await apiClient.getClient().post<{ valid: boolean; errors: string[] }>(
      `${PIPELINES_BASE}/${id}/validate/`,
    );
    return resp.data;
  },

  async listExecutions(
    filters: TransformationListFilters = {},
  ): Promise<PaginatedResponse<PipelineExecution>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', String(filters.page));
    if (filters.page_size) params.append('page_size', String(filters.page_size));
    if (filters.status) params.append('status', filters.status);
    const url = params.toString()
      ? `${EXECUTIONS_BASE}/?${params}`
      : `${EXECUTIONS_BASE}/`;
    const resp = await apiClient.getClient().get<PaginatedResponse<PipelineExecution>>(url);
    return resp.data;
  },

  async getExecution(id: string): Promise<PipelineExecution> {
    const resp = await apiClient.getClient().get<PipelineExecution>(
      `${EXECUTIONS_BASE}/${id}/`,
    );
    return resp.data;
  },
};
