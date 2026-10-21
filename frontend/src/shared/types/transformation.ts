/**
 * Transformation Types — Phase 115D
 * Based on hub/apps/transformation/models.py
 */

export const PipelineStatus = {
  DRAFT: 'DRAFT',
  ACTIVE: 'ACTIVE',
  INACTIVE: 'INACTIVE',
  ARCHIVED: 'ARCHIVED',
} as const;
export type PipelineStatus = (typeof PipelineStatus)[keyof typeof PipelineStatus];

export const ExecutionStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const;
export type ExecutionStatus = (typeof ExecutionStatus)[keyof typeof ExecutionStatus];

export const ExecutionMode = {
  SYNC: 'SYNC',
  ASYNC: 'ASYNC',
  SCHEDULED: 'SCHEDULED',
  MANUAL: 'MANUAL',
  AUTOMATED: 'AUTOMATED',
} as const;
export type ExecutionMode = (typeof ExecutionMode)[keyof typeof ExecutionMode];

export interface PipelineStep {
  name: string;
  type: string;
  config?: Record<string, unknown>;
}

export interface PipelineDefinition {
  version: string;
  steps: PipelineStep[];
}

export interface TransformationPipeline {
  id: string;
  name: string;
  description?: string | null;
  status: PipelineStatus;
  version: string;
  pipeline_definition: PipelineDefinition;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PipelineExecution {
  id: string;
  pipeline: string;
  asset: string;
  execution_mode: ExecutionMode;
  status: ExecutionStatus;
  started_at?: string | null;
  completed_at?: string | null;
  metrics?: Record<string, unknown>;
  execution_log?: Array<Record<string, unknown>>;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransformationPipelineCreateRequest {
  name: string;
  description?: string;
  pipeline_definition: PipelineDefinition;
  version?: string;
  metadata?: Record<string, unknown>;
}

export interface TransformationPipelineUpdateRequest {
  name?: string;
  description?: string;
  pipeline_definition?: PipelineDefinition;
  status?: PipelineStatus;
  metadata?: Record<string, unknown>;
}

export interface PipelineExecuteRequest {
  asset_id: string;
  execution_mode?: ExecutionMode;
}

export interface TransformationListFilters {
  page?: number;
  page_size?: number;
  status?: PipelineStatus;
  search?: string;
  ordering?: string;
}
