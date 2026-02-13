/**
 * Data Quality Types
 * Based on backend DQRunSerializer and DQRun model
 */

export const DQRunStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  SUCCEEDED: 'SUCCEEDED',
  FAILED: 'FAILED',
} as const;
export type DQRunStatus = (typeof DQRunStatus)[keyof typeof DQRunStatus];

export const DQOverallStatus = {
  PASS: 'PASS',
  FAIL: 'FAIL',
  WARN: 'WARN',
  UNKNOWN: 'UNKNOWN',
} as const;
export type DQOverallStatus = (typeof DQOverallStatus)[keyof typeof DQOverallStatus];

export const DQEngine = {
  GREAT_EXPECTATIONS: 'GREAT_EXPECTATIONS',
  SODA: 'SODA',
} as const;
export type DQEngine = (typeof DQEngine)[keyof typeof DQEngine];

export interface DQCheck {
  name: string;
  type: string;
  status: 'PASS' | 'FAIL' | 'WARN' | 'UNKNOWN';
  result: {
    observed_value?: unknown;
    expected_value?: unknown;
    message?: string;
  };
  expectation?: string;
}

export interface DQRun {
  id: string;
  tenant: string;
  asset?: string;
  dataset?: string;
  file?: string;
  job: string;
  profile_key: string;
  engine: DQEngine;
  status: DQRunStatus;
  overall_status?: DQOverallStatus;
  quality_score?: number;
  checks_json?: DQCheck[];
  details_json?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface DQRunCreateRequest {
  asset_id?: string;
  dataset_id?: string;
  file_id?: string;
  profile_key?: string;
}

export interface DQRunListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  status?: DQRunStatus;
  dataset_id?: string;
  date_from?: string;
  date_to?: string;
}

export interface DQRunResults {
  dq_run_id: string;
  overall_status?: DQOverallStatus;
  quality_score?: number;
  score_breakdown: {
    total_checks: number;
    passed_checks: number;
    failed_checks: number;
    warning_checks: number;
    pass_rate: number;
    overall_score: number;
    by_category: Record<string, {
      total: number;
      passed: number;
      failed: number;
      warnings: number;
    }>;
  };
  checks: DQCheck[];
  check_details: Array<{
    name: string;
    type: string;
    status: string;
    result: Record<string, unknown>;
    expectation?: string;
    observed_value?: unknown;
    expected_value?: unknown;
    message?: string;
    severity: 'HIGH' | 'MEDIUM' | 'LOW';
  }>;
  trend_analysis?: {
    direction: string;
    change_percentage: number;
    previous_value: number;
    current_value: number;
    period_days: number;
    created_at: string;
  };
  anomalies?: Array<{
    metric_type: string;
    expected_value: number;
    actual_value: number;
    deviation: number;
    severity: string;
    detected_at: string;
  }>;
  recommendations?: Array<{
    check_name: string;
    check_type: string;
    issue: string;
    priority: string;
    suggestion: string;
  }>;
  engine_type: string;
  engine_version?: string;
  profile_key: string;
  metadata?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
}
