/**
 * Databricks control-plane types — openspec add-databricks-control-plane.
 * Based on hub/apps/databricks_admin/{models,serializers}.py
 */

export const DatabricksCloud = {
  AWS: 'AWS',
  AZURE: 'AZURE',
  GCP: 'GCP',
} as const;
export type DatabricksCloud = (typeof DatabricksCloud)[keyof typeof DatabricksCloud];

export const DatabricksWorkspaceStatus = {
  REGISTERED: 'REGISTERED',
  CONNECTING: 'CONNECTING',
  ACTIVE: 'ACTIVE',
  ERROR: 'ERROR',
  DISABLED: 'DISABLED',
} as const;
export type DatabricksWorkspaceStatus =
  (typeof DatabricksWorkspaceStatus)[keyof typeof DatabricksWorkspaceStatus];

export const DatabricksCredentialAuthMode = {
  PAT: 'PAT',
  OAUTH_M2M: 'OAUTH_M2M',
} as const;
export type DatabricksCredentialAuthMode =
  (typeof DatabricksCredentialAuthMode)[keyof typeof DatabricksCredentialAuthMode];

export interface DatabricksWorkspace {
  id: string;
  tenant: string;
  name: string;
  host: string;
  cloud: DatabricksCloud;
  region: string;
  metastore_id: string | null;
  status: DatabricksWorkspaceStatus;
  status_display: string;
  created_at: string;
  updated_at: string;
}

export interface DatabricksWorkspaceCreatePayload {
  name: string;
  host: string;
  cloud: DatabricksCloud;
  region: string;
  metastore_id?: string;
}

/** ``config`` is write-only on the wire — never returned. */
export interface DatabricksCredential {
  id: string;
  workspace: string;
  auth_mode: DatabricksCredentialAuthMode;
  auth_mode_display: string;
  expires_at: string | null;
  last_rotated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DatabricksCredentialCreatePayload {
  auth_mode: DatabricksCredentialAuthMode;
  config: { token: string } | { client_id: string; client_secret: string };
}

export interface DatabricksTestResult {
  status: 'ok';
  latency_ms: number;
}

// ── UC mirror browse (openspec add-databricks-control-plane task 1.9) ──

/** Mirror object kinds for the schema-scoped browse listings. */
export const UC_OBJECT_KINDS = ['tables', 'views', 'volumes', 'models'] as const;
export type UCObjectKind = (typeof UC_OBJECT_KINDS)[number];

/** Effective permissions payload (UC REST `effective-permissions` shape). */
export interface UCPrivilegeAssignment {
  principal: string;
  privileges: string[];
}

export interface UCEffectivePermissions {
  privilege_assignments?: UCPrivilegeAssignment[];
}

/** The 1.3 mirror listing rows (id/name/full_name + surface fields). */
export interface UCCatalog {
  id: string;
  name: string;
  catalog_type: string;
  comment?: string;
  properties?: Record<string, unknown>;
  owner?: string;
  full_name: string;
  synced_at: string | null;
}

export interface UCSchema {
  id: string;
  name: string;
  comment?: string;
  owner?: string;
  full_name: string;
  synced_at: string | null;
}

export interface UCTable {
  id: string;
  name: string;
  table_type: string;
  columns?: Array<Record<string, unknown>>;
  comment?: string;
  owner?: string;
  full_name: string;
  /** The UC tables API's reported tags (list of {key, value}) — the
   * feature_store convention reads this (12.3). */
  tags?: Array<{ key: string; value: string }>;
  synced_at: string | null;
}

export interface UCExternalLocation {
  id: string;
  name: string;
  url: string;
  credential_name: string;
  owner?: string;
  full_name: string;
  synced_at: string | null;
}

export interface UCStorageCredential {
  id: string;
  name: string;
  comment?: string;
  owner?: string;
  full_name: string;
  synced_at: string | null;
}

/** Table detail: mirror columns + metadata + LIVE effective permissions. */
export interface UCTableDetail extends UCTable {
  catalog: string;
  schema: string;
  effective_permissions: UCEffectivePermissions | null;
}

export const SqlWarehouseState = {
  STARTING: 'STARTING',
  RUNNING: 'RUNNING',
  STOPPING: 'STOPPING',
  STOPPED: 'STOPPED',
  DELETING: 'DELETING',
} as const;
export type SqlWarehouseState = (typeof SqlWarehouseState)[keyof typeof SqlWarehouseState];

/** The 3.2 mirror row shape (the 3.7 endpoints' wire contract). */
export interface SqlWarehouse {
  warehouse_id: string;
  name: string;
  state: SqlWarehouseState;
  serverless: boolean;
  size: string | null;
  auto_stop_mins: number;
}

/** The 4.2 job-run lifecycle vocabulary (reported verbatim, never invented). */
export const DatabricksJobRunLifecycleState = {
  PENDING: 'PENDING',
  QUEUED: 'QUEUED',
  RUNNING: 'RUNNING',
  TERMINATING: 'TERMINATING',
  TERMINATED: 'TERMINATED',
  SKIPPED: 'SKIPPED',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  WAITING_FOR_RETRY: 'WAITING_FOR_RETRY',
  BLOCKED: 'BLOCKED',
} as const;
export type DatabricksJobRunLifecycleState =
  (typeof DatabricksJobRunLifecycleState)[keyof typeof DatabricksJobRunLifecycleState];

/** The 4.2 run result vocabulary (reported verbatim at termination). */
export const DatabricksJobRunResultState = {
  SUCCESS: 'SUCCESS',
  FAILED: 'FAILED',
  TIMEDOUT: 'TIMEDOUT',
  CANCELED: 'CANCELED',
  MAXIMUM_CONCURRENT_RUNS_REACHED: 'MAXIMUM_CONCURRENT_RUNS_REACHED',
  EXCLUDED: 'EXCLUDED',
  SUCCESS_WITH_FAILURES: 'SUCCESS_WITH_FAILURES',
  UPSTREAM_FAILED: 'UPSTREAM_FAILED',
  UPSTREAM_CANCELED: 'UPSTREAM_CANCELED',
} as const;
export type DatabricksJobRunResultState =
  (typeof DatabricksJobRunResultState)[keyof typeof DatabricksJobRunResultState];

/** The 4.2 job mirror row shape (the 4.5 endpoints' wire contract). */
export interface DatabricksJob {
  job_id: string;
  name: string;
  task_config: unknown[] | Record<string, unknown>;
  schedule: Record<string, unknown> | null;
  synced_at: string | null;
}

/** The 4.2 run mirror row shape (the 4.5 endpoints' wire contract). */
export interface DatabricksJobRun {
  run_id: string;
  lifecycle_state: DatabricksJobRunLifecycleState;
  result_state: DatabricksJobRunResultState | null;
  duration_ms: number | null;
  error_message: string | null;
  synced_at: string | null;
}

/** The 7.6 cost-budget row (the budgets endpoint's wire contract) —
 * the U9 budget page progress bar feeds these fields directly. */
export interface DatabricksCostBudgetBreakdownEntry {
  warehouse_id: string | null;
  warehouse_name: string | null;
  units: string;
}

export interface DatabricksCostBudget {
  id: string;
  warehouse_id: string | null;
  warehouse_name: string | null;
  budget_units_per_hour: string | null;
  enforcement_mode: 'BLOCK' | 'ALERT';
  consumed: string;
  ratio: number | null;
  percent: number | null;
  window_seconds: number;
  breakdown: DatabricksCostBudgetBreakdownEntry[];
}

/**
 * The 10.2 DLT pipeline mirror row (the 10.7 list endpoint's wire
 * contract) — every state is the pipelines API's REPORTED value.
 */
export interface DatabricksDltPipeline {
  id: string;
  pipeline_id: string;
  name: string;
  state: 'IDLE' | 'ACTIVE' | 'DELETING' | 'FAILED' | 'DELETED';
  channel: 'CURRENT' | 'PREVIEW' | null;
  settings: Record<string, unknown>;
  synced_at: string | null;
  latest_update_id: string | null;
  latest_update_state: string | null;
}

/** A mirrored UC registered model (openspec add-databricks-ml-assets
 * task 12.6 — the ML-assets page's model listing). */
export interface UCModelSummary {
  id: string;
  name: string;
  full_name: string;
  comment?: string;
  owner?: string;
  aliases: Array<{ alias_name: string; version_num: number }>;
  latest_version: number;
  synced_at: string | null;
}

/** A mirrored ML serving/vector-search endpoint (12.4 mirror). */
export interface DatabricksMlServingEndpoint {
  id: string;
  name: string;
  endpoint_type: 'SERVING' | 'VECTOR';
  state: string;
  config: Record<string, unknown>;
  synced_at: string | null;
}
