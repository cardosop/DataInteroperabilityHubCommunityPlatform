/**
 * Scheduled Ingestion Types
 * Aligned with backend ScheduledIngestionSerializer and ScheduledIngestionRunSerializer.
 * Run detail includes optional prefect_flow_run_id for Prefect-executed runs (Phase 4).
 */

export type SourceType =
  | 'S3'
  | 'GCS'
  | 'AZURE_BLOB'
  | 'HTTP'
  | 'HTTPS'
  | 'FTP'
  | 'SFTP'
  | 'DATABASE'
  | 'SNOWFLAKE_SOURCE'
  | 'BIGQUERY_SOURCE'
  | 'DATABRICKS_SOURCE'
  | 'ATHENA_SOURCE';

export type ScheduleType = 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'CUSTOM_CRON';

export type ScheduledIngestionStatus = 'ACTIVE' | 'PAUSED' | 'ERROR';

export type DeploymentSyncStatus = 'SYNCED' | 'PENDING' | 'FAILED';

export type ScheduledIngestionRunStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export interface ScheduledIngestion {
  id: string;
  tenant: string;
  tenant_name: string;
  name: string;
  description: string | null;
  source_type: SourceType;
  source_config: Record<string, unknown>;
  schedule_type: ScheduleType;
  schedule_config: Record<string, unknown>;
  file_pattern: string | null;
  asset: string | null;
  asset_id?: string; // write-only
  asset_name: string | null;
  contract: string | null;
  contract_name: string | null;
  auto_create_asset: boolean;
  auto_activate: boolean;
  status: ScheduledIngestionStatus;
  next_run_at: string | null;
  prefect_deployment_id: string | null;
  prefect_work_pool_name: string;
  last_processed_file: string | null;
  last_processed_timestamp: string | null;
  ingestion_state: Record<string, unknown> | null;
  error_message: string | null;
  credential_ref: string | null;
  created_by: string;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledIngestionRun {
  id: string;
  scheduled_ingestion: string;
  scheduled_ingestion_name: string;
  status: ScheduledIngestionRunStatus;
  started_at: string | null;
  completed_at: string | null;
  prefect_flow_run_id: string | null;
  job_id: string | null;
  files_found: number | null;
  files_processed: number | null;
  files_failed: number | null;
  datasets_created: number | null;
  error_message: string | null;
  result_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledIngestionListFilters {
  page?: number;
  page_size?: number;
  status?: ScheduledIngestionStatus;
}

export interface ScheduledIngestionCreateRequest {
  name: string;
  description?: string;
  source_type: SourceType;
  source_config: Record<string, unknown>;
  schedule_type: ScheduleType;
  schedule_config: Record<string, unknown>;
  file_pattern?: string;
  asset_id?: string;
  contract?: string;
  auto_create_asset?: boolean;
  auto_activate?: boolean;
  status?: ScheduledIngestionStatus;
  prefect_work_pool_name?: string;
  credential_ref?: string;
  test_connection?: boolean;
}

export interface ScheduledIngestionUpdateRequest {
  name?: string;
  description?: string;
  source_type?: SourceType;
  source_config?: Record<string, unknown>;
  schedule_type?: ScheduleType;
  schedule_config?: Record<string, unknown>;
  file_pattern?: string;
  asset_id?: string;
  contract?: string;
  auto_create_asset?: boolean;
  auto_activate?: boolean;
  status?: ScheduledIngestionStatus;
  credential_ref?: string;
  prefect_work_pool_name?: string;
}

export interface ScheduledIngestionTriggerRequest {
  parameters?: Record<string, unknown>;
}

export interface ScheduledIngestionTriggerResponse {
  scheduled_ingestion_id: string;
  run_id: string;
  flow_run_id: string;
  status: string;
  message: string;
}

export interface ScheduledIngestionListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScheduledIngestion[];
}
