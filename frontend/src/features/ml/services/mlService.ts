/**
 * ML Service
 * API client for ML/ODH operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  MLModel,
  MLModelCreateRequest,
  MLModelUpdateRequest,
  TrainingJob,
  TrainingJobSubmitRequest,
  InferenceDeployment,
  InferenceDeployRequest,
  InferenceMetrics,
  MLListFilters,
} from '../../../shared/types/ml';

const ML_BASE_PATH = 'ml';

export const mlService = {
  /**
   * List ML models
   */
  async listModels(filters: MLListFilters = {}): Promise<PaginatedResponse<MLModel>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.model_type) params.append('model_type', filters.model_type);
    if (filters.status) params.append('status', filters.status);
    if (filters.asset_id) params.append('asset_id', filters.asset_id);

    const response = await apiClient.getClient().get<PaginatedResponse<MLModel>>(
      `${ML_BASE_PATH}/models/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get model by ID
   */
  async getModel(id: string): Promise<MLModel> {
    const response = await apiClient.getClient().get<MLModel>(`${ML_BASE_PATH}/models/${id}/`);
    return response.data;
  },

  /**
   * Create model
   */
  async createModel(data: MLModelCreateRequest): Promise<MLModel> {
    const response = await apiClient.getClient().post<MLModel>(`${ML_BASE_PATH}/models/`, data);
    return response.data;
  },

  /**
   * Update model
   */
  async updateModel(id: string, data: MLModelUpdateRequest): Promise<MLModel> {
    const response = await apiClient.getClient().patch<MLModel>(`${ML_BASE_PATH}/models/${id}/`, data);
    return response.data;
  },

  /**
   * Delete model
   */
  async deleteModel(id: string): Promise<void> {
    await apiClient.getClient().delete(`${ML_BASE_PATH}/models/${id}/`);
  },

  /**
   * List training jobs
   */
  async listTrainingJobs(filters: MLListFilters = {}): Promise<PaginatedResponse<TrainingJob>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.model_id) params.append('model_id', filters.model_id);
    if (filters.status) params.append('status', filters.status);

    const response = await apiClient.getClient().get<PaginatedResponse<TrainingJob>>(
      `${ML_BASE_PATH}/training/jobs/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get training job by ID
   */
  async getTrainingJob(id: string): Promise<TrainingJob> {
    const response = await apiClient.getClient().get<TrainingJob>(`${ML_BASE_PATH}/training/jobs/${id}/`);
    return response.data;
  },

  /**
   * Submit training job
   */
  async submitTrainingJob(data: TrainingJobSubmitRequest): Promise<TrainingJob> {
    const response = await apiClient.getClient().post<TrainingJob>(`${ML_BASE_PATH}/training/jobs/`, data);
    return response.data;
  },

  /**
   * Cancel training job
   */
  async cancelTrainingJob(id: string): Promise<void> {
    await apiClient.getClient().post(`${ML_BASE_PATH}/training/jobs/${id}/cancel/`);
  },

  /**
   * Get training job logs
   */
  async getTrainingJobLogs(id: string, lines?: number): Promise<string> {
    const params = new URLSearchParams();
    if (lines) params.append('lines', lines.toString());

    const response = await apiClient.getClient().get<string>(
      `${ML_BASE_PATH}/training/jobs/${id}/logs/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * List inference deployments
   */
  async listInferenceDeployments(filters: MLListFilters = {}): Promise<PaginatedResponse<InferenceDeployment>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.model_id) params.append('model_id', filters.model_id);
    if (filters.status) params.append('status', filters.status);

    const response = await apiClient.getClient().get<PaginatedResponse<InferenceDeployment>>(
      `${ML_BASE_PATH}/inference/deployments/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get inference deployment by ID
   */
  async getInferenceDeployment(id: string): Promise<InferenceDeployment> {
    const response = await apiClient.getClient().get<InferenceDeployment>(
      `${ML_BASE_PATH}/inference/deployments/${id}/`
    );
    return response.data;
  },

  /**
   * Deploy model for inference
   */
  async deployInference(data: InferenceDeployRequest): Promise<InferenceDeployment> {
    const response = await apiClient.getClient().post<InferenceDeployment>(
      `${ML_BASE_PATH}/inference/deployments/`,
      data
    );
    return response.data;
  },

  /**
   * Undeploy inference deployment
   */
  async undeployInference(id: string): Promise<void> {
    await apiClient.getClient().delete(`${ML_BASE_PATH}/inference/deployments/${id}/`);
  },

  /**
   * Get inference metrics
   */
  async getInferenceMetrics(id: string, startTime?: string, endTime?: string): Promise<InferenceMetrics> {
    const params = new URLSearchParams();
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);

    const response = await apiClient.getClient().get<InferenceMetrics>(
      `${ML_BASE_PATH}/inference/deployments/${id}/metrics/?${params.toString()}`
    );
    return response.data;
  },
};
