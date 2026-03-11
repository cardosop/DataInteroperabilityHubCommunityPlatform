/**
 * Transformation Pipeline Service
 * API client for transformation pipeline operations (placeholder backend)
 */

import { apiClient } from '../../../shared/api/client';

export interface TransformationPipeline {
  id: string;
  name: string;
  status: string;
}

export interface TransformationPipelineListResponse {
  results: TransformationPipeline[];
  count: number;
}

const PIPELINES_BASE_PATH = 'transformation/pipelines';

export const transformationService = {
  /**
   * List transformation pipelines
   */
  async list(): Promise<TransformationPipelineListResponse> {
    const response = await apiClient
      .getClient()
      .get<TransformationPipelineListResponse>(`${PIPELINES_BASE_PATH}/`);
    return response.data;
  },

  /**
   * Get pipeline by ID (placeholder backend returns 404 for all ids)
   */
  async getById(id: string): Promise<TransformationPipeline> {
    const response = await apiClient
      .getClient()
      .get<TransformationPipeline>(`${PIPELINES_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new pipeline (placeholder returns id but does not persist)
   */
  async create(data: { name?: string }): Promise<TransformationPipeline> {
    const response = await apiClient
      .getClient()
      .post<TransformationPipeline>(`${PIPELINES_BASE_PATH}/`, data);
    return response.data;
  },
};
