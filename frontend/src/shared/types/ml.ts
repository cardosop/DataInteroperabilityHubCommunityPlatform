/**
 * ML/ODH Types
 * Based on backend ML models and serializers
 */

export const ModelType = {
  CLASSIFICATION: 'CLASSIFICATION',
  REGRESSION: 'REGRESSION',
  CLUSTERING: 'CLUSTERING',
  NLP: 'NLP',
  COMPUTER_VISION: 'COMPUTER_VISION',
  RECOMMENDATION: 'RECOMMENDATION',
  TIME_SERIES: 'TIME_SERIES',
  ANOMALY_DETECTION: 'ANOMALY_DETECTION',
  OTHER: 'OTHER',
} as const;
export type ModelType = (typeof ModelType)[keyof typeof ModelType];

export const ModelStatus = {
  TRAINING: 'TRAINING',
  TRAINED: 'TRAINED',
  DEPLOYED: 'DEPLOYED',
  FAILED: 'FAILED',
  ARCHIVED: 'ARCHIVED',
} as const;
export type ModelStatus = (typeof ModelStatus)[keyof typeof ModelStatus];

export const TrainingJobStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const;
export type TrainingJobStatus = (typeof TrainingJobStatus)[keyof typeof TrainingJobStatus];

export const InferenceDeploymentStatus = {
  DEPLOYING: 'DEPLOYING',
  DEPLOYED: 'DEPLOYED',
  FAILED: 'FAILED',
  UNDEPLOYED: 'UNDEPLOYED',
} as const;
export type InferenceDeploymentStatus = (typeof InferenceDeploymentStatus)[keyof typeof InferenceDeploymentStatus];

export interface MLModel {
  id: string;
  odh_model_id: string;
  odh_model_name: string;
  odh_model_version: string;
  asset_id?: string | null;
  contract_id?: string | null;
  model_type: ModelType;
  status: ModelStatus;
  training_dataset_id?: string | null;
  training_job_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MLModelCreateRequest {
  odh_model_id: string;
  odh_model_name: string;
  odh_model_version: string;
  model_type: ModelType;
  asset_id?: string;
  contract_id?: string;
}

export interface MLModelUpdateRequest {
  asset_id?: string;
  contract_id?: string;
  status?: ModelStatus;
}

export interface TrainingJob {
  id: string;
  model_id: string;
  dataset_id: string;
  status: TrainingJobStatus;
  config?: Record<string, unknown>;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TrainingJobSubmitRequest {
  model_id: string;
  dataset_id: string;
  config?: Record<string, unknown>;
}

export interface InferenceDeployment {
  id: string;
  model_id: string;
  status: InferenceDeploymentStatus;
  replicas?: number;
  endpoint?: string;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface InferenceDeployRequest {
  model_id: string;
  config?: Record<string, unknown>;
}

export interface InferenceMetrics {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  error_rate: number;
  average_latency_ms: number;
  accuracy?: number;
}

export interface MLListFilters {
  page?: number;
  page_size?: number;
  model_type?: ModelType;
  status?: ModelStatus | TrainingJobStatus | InferenceDeploymentStatus;
  asset_id?: string;
  model_id?: string;
}
