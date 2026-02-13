/**
 * Virtualization Types
 * Based on backend VirtualDatasetSerializer and QueryExecutionSerializer
 */

export const QueryType = {
  SQL: 'SQL',
  SPARQL: 'SPARQL',
  FEDERATED: 'FEDERATED',
  GRAPHQL: 'GRAPHQL',
  REST: 'REST',
} as const;
export type QueryType = (typeof QueryType)[keyof typeof QueryType];

export const VirtualDatasetStatus = {
  DRAFT: 'DRAFT',
  ACTIVE: 'ACTIVE',
  INACTIVE: 'INACTIVE',
  ARCHIVED: 'ARCHIVED',
} as const;
export type VirtualDatasetStatus = (typeof VirtualDatasetStatus)[keyof typeof VirtualDatasetStatus];

export const QueryExecutionStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
} as const;
export type QueryExecutionStatus = (typeof QueryExecutionStatus)[keyof typeof QueryExecutionStatus];

export const QueryExecutionMode = {
  SYNC: 'SYNC',
  ASYNC: 'ASYNC',
  SCHEDULED: 'SCHEDULED',
  MANUAL: 'MANUAL',
  AUTOMATED: 'AUTOMATED',
} as const;
export type QueryExecutionMode = (typeof QueryExecutionMode)[keyof typeof QueryExecutionMode];

export interface VirtualDataset {
  id: string;
  tenant: string;
  created_by?: string;
  name: string;
  description?: string;
  query: string;
  query_type: QueryType;
  schema?: Record<string, any>;
  sources?: any[];
  version: string;
  status: VirtualDatasetStatus;
  created_at: string;
  updated_at: string;
}

export interface VirtualDatasetCreateRequest {
  name: string;
  description?: string;
  query: string;
  query_type: QueryType;
  schema?: Record<string, any>;
  sources?: any[];
  version?: string;
  status?: VirtualDatasetStatus;
}

export interface VirtualDatasetUpdateRequest {
  name?: string;
  description?: string;
  query?: string;
  query_type?: QueryType;
  schema?: Record<string, any>;
  sources?: any[];
  version?: string;
  status?: VirtualDatasetStatus;
}

export interface VirtualDatasetListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  status?: VirtualDatasetStatus;
  query_type?: QueryType;
  owner?: string;
  created_by?: string;
}

export interface VirtualDatasetValidationResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  details: Record<string, any>;
}

export interface VirtualDatasetVersion {
  version: string;
  status: VirtualDatasetStatus;
  created_at: string;
  updated_at: string;
  query_type: QueryType;
  source_count: number;
}

export interface QueryExecution {
  id: string;
  virtual_dataset: string;
  virtual_dataset_name: string;
  query: string;
  parameters?: Record<string, any>;
  execution_mode: QueryExecutionMode;
  status: QueryExecutionStatus;
  started_at?: string;
  completed_at?: string;
  result_cache_key?: string;
  result_storage_path?: string;
  execution_log?: string;
  metrics?: Record<string, any>;
  job?: string;
  created_at: string;
  updated_at: string;
}

export interface QueryExecutionCreateRequest {
  parameters?: Record<string, any>;
  execution_mode?: QueryExecutionMode;
  force_async?: boolean;
  timeout_seconds?: number;
}

export interface QueryExecutionResult {
  execution_id: string;
  data: any;
  total_count: number;
  returned_count: number;
  format: string;
  content_type: string;
  pagination?: {
    page: number;
    page_size: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
  stream_enabled: boolean;
  stream_url?: string;
}

export interface QueryExecutionProgress {
  execution_id: string;
  status: QueryExecutionStatus;
  progress_percentage?: number;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  metrics?: Record<string, any>;
  latest_logs?: Array<Record<string, any>>;
}

export interface QueryExecutionCancelResponse {
  execution_id: string;
  status: QueryExecutionStatus;
  message: string;
}

export interface QueryExecutionListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  status?: QueryExecutionStatus;
  virtual_dataset?: string;
}
