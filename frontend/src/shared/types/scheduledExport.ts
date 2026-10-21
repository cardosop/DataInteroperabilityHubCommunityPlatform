/**
 * Scheduled Export Types
 * Aligned with backend ScheduledExportSerializer and ScheduledExportRunSerializer.
 * Run detail includes optional prefect_flow_run_id for Prefect-executed runs.
 */

export type DestinationType = 'S3' | 'GCS' | 'AZURE_BLOB';

export type ScheduledExportStatus = 'ACTIVE' | 'PAUSED' | 'ERROR';

export type ScheduledExportRunStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface ScheduledExport {
  id: string;
  tenant: string;
  tenant_name: string;
  name: string;
  schedule_config: {
    cron: string;
    timezone?: string;
  };
  destination_type: DestinationType;
  destination_config: Record<string, unknown>;
  source_scope: {
    asset_ids?: string[];
    dataset_ids?: string[];
    file_ids?: string[];
    contract_id?: string;
  };
  status: ScheduledExportStatus;
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_status: ScheduledExportRunStatus | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledExportRun {
  id: string;
  scheduled_export: string;
  scheduled_export_name: string;
  status: ScheduledExportRunStatus;
  items_found: number | null;
  items_exported: number | null;
  items_failed: number | null;
  result_json: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  prefect_flow_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledExportListFilters {
  page?: number;
  page_size?: number;
  status?: ScheduledExportStatus;
}

export interface ScheduledExportCreateRequest {
  name: string;
  schedule_config: {
    cron: string;
    timezone?: string;
  };
  destination_type: DestinationType;
  destination_config: Record<string, unknown>;
  source_scope: {
    asset_ids?: string[];
    dataset_ids?: string[];
    file_ids?: string[];
    contract_id?: string;
  };
  status?: ScheduledExportStatus;
}

export interface ScheduledExportUpdateRequest {
  name?: string;
  schedule_config?: {
    cron: string;
    timezone?: string;
  };
  destination_type?: DestinationType;
  destination_config?: Record<string, unknown>;
  source_scope?: {
    asset_ids?: string[];
    dataset_ids?: string[];
    file_ids?: string[];
    contract_id?: string;
  };
  status?: ScheduledExportStatus;
}

export interface ScheduledExportTriggerRequest {
  parameters?: Record<string, unknown>;
}

export interface ScheduledExportTriggerResponse {
  scheduled_export_id: string;
  flow_run_id: string;
  status: string;
  message: string;
}

export interface ScheduledExportListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: ScheduledExport[];
}
