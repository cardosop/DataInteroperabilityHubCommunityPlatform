/**
 * Job Types
 * Based on backend JobSerializer and Job model
 */

export const JobStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const;
export type JobStatus = (typeof JobStatus)[keyof typeof JobStatus];

export const JobType = {
  DQ_RUN: 'DQ_RUN',
  COMPLIANCE_RUN: 'COMPLIANCE_RUN',
  SCHEMA_INFERENCE: 'SCHEMA_INFERENCE',
  VIRTUAL_QUERY_EXECUTION: 'VIRTUAL_QUERY_EXECUTION',
  MARKETPLACE_SYNC: 'MARKETPLACE_SYNC',
  ODPS_GENERATION: 'ODPS_GENERATION',
} as const;
export type JobType = (typeof JobType)[keyof typeof JobType];

export const ResourceType = {
  ASSET: 'ASSET',
  DATASET: 'DATASET',
  CONTRACT: 'CONTRACT',
  FILE: 'FILE',
} as const;
export type ResourceType = (typeof ResourceType)[keyof typeof ResourceType];

export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  resource_type: ResourceType;
  resource_id: string;
  details_json?: Record<string, unknown>;
  result_json?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  tenant_id: string;
  created_by: string;
}

export interface JobCreateRequest {
  type: JobType;
  resource_type: ResourceType;
  resource_id: string;
  details_json?: Record<string, unknown>;
}

export interface JobListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  type?: JobType;
  status?: JobStatus;
  resource_type?: ResourceType;
  resource_id?: string;
}

export interface JobProgress {
  job_id: string;
  status: JobStatus;
  progress_percentage?: number;
  current_step?: string;
  total_steps?: number;
  message?: string;
  error?: string;
}
