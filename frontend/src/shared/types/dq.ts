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

/**
 * Canonical DQ dimensions (Phase 240.3.C — six-dimension coverage).
 *
 * Mirror of the backend ``DQCategory`` enum in
 * ``services/dq-service/dq_profile.py``.  ACCURACY / CONSISTENCY /
 * TIMELINESS were added in Phase 240.3.C alongside the corresponding
 * pandas-native checks; the ``intake_basic_*`` profiles include
 * zero-config versions of all three (degrade to WARN per D240.12 when
 * the data lacks a reference dataset / derivation rules / timestamp
 * column).
 *
 * The frontend uses this constant to populate the category filter
 * dropdown so users can see ALL dimensions even before encountering
 * a check that emits one.
 */
export const DQCategory = {
  COMPLETENESS: 'COMPLETENESS',
  VALIDITY: 'VALIDITY',
  UNIQUENESS: 'UNIQUENESS',
  CONSISTENCY: 'CONSISTENCY',
  ACCURACY: 'ACCURACY',
  TIMELINESS: 'TIMELINESS',
} as const;
export type DQCategory = (typeof DQCategory)[keyof typeof DQCategory];

/**
 * Six canonical DQ dimensions in display order — used by the
 * ``DQRunResultsViewer`` category filter dropdown.
 */
export const DQ_CATEGORIES: readonly DQCategory[] = [
  DQCategory.COMPLETENESS,
  DQCategory.VALIDITY,
  DQCategory.UNIQUENESS,
  DQCategory.CONSISTENCY,
  DQCategory.ACCURACY,
  DQCategory.TIMELINESS,
] as const;

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

// ─────────────────────────────────────────────────────────────────────
// Phase 240.4.A — advanced quality endpoint shapes.
// Mirror the backend ``DQQualityViewSet`` response payloads in
// ``hub/apps/dq/views.py``.
// ─────────────────────────────────────────────────────────────────────

export const DQAnomalySeverity = {
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
  LOW: 'LOW',
} as const;
export type DQAnomalySeverity = (typeof DQAnomalySeverity)[keyof typeof DQAnomalySeverity];

export const DQ_SEVERITIES: readonly DQAnomalySeverity[] = [
  DQAnomalySeverity.CRITICAL,
  DQAnomalySeverity.HIGH,
  DQAnomalySeverity.MEDIUM,
  DQAnomalySeverity.LOW,
] as const;

export interface DQAnomaly {
  id: string;
  tenant_id: string;
  asset_id: string | null;
  dataset_id: string | null;
  dq_run_id: string | null;
  metric_type: string;
  expected_value: number | null;
  actual_value: number;
  deviation: number;
  severity: DQAnomalySeverity;
  anomaly_type: string;
  description: string | null;
  metadata: Record<string, unknown> | null;
  detected_at: string | null;
  acknowledged: boolean;
}

export interface DQAnomaliesFilters {
  asset_id?: string;
  dataset_id?: string;
  severity?: DQAnomalySeverity;
  since?: string;
}

export const DQTrendDirection = {
  IMPROVING: 'IMPROVING',
  DEGRADING: 'DEGRADING',
  STABLE: 'STABLE',
} as const;
export type DQTrendDirection = (typeof DQTrendDirection)[keyof typeof DQTrendDirection];

export interface DQTrendPoint {
  period_start: string;
  period_end: string;
  current_value: number;
  previous_value: number | null;
  change_amount: number | null;
  change_percent: number | null;
  direction: DQTrendDirection;
  trend_strength: number | null;
  forecast_value: number | null;
}

export interface DQTrendsFilters {
  asset_id?: string;
  dataset_id?: string;
  metric_type?: string;
  time_range?: number;
  period_type?: 'HOURLY' | 'DAILY' | 'WEEKLY' | 'MONTHLY';
}

/** Tenant-level executive dashboard payload from ``GET /api/v1/dq/quality/scorecards/`` (no asset_id). */
export interface DQExecutiveDashboard {
  period: { start: string; end: string; days: number };
  summary: {
    total_runs: number;
    avg_quality_score: number;
    pass_rate: number;
    fail_rate: number;
    warn_count: number;
  };
  score_distribution: Record<string, number>;
  top_issues: Array<{ issue: string; count: number; percentage: number }>;
  trend_summary: {
    improving: number;
    degrading: number;
    stable: number;
    improving_percent: number;
    degrading_percent: number;
  };
}

/** Asset-level scorecard payload from ``GET /api/v1/dq/quality/scorecards/?asset_id=...``. */
export interface DQAssetScorecard {
  asset_id: string;
  period: { start: string; end: string; days: number };
  metrics: {
    total_runs: number;
    avg_quality_score: number;
    pass_rate: number;
    fail_rate: number;
  };
  recent_runs: Array<{
    id: string;
    quality_score: number | null;
    overall_status: string | null;
    completed_at: string | null;
  }>;
  trends: Array<{
    period_start: string;
    current_value: number;
    direction: DQTrendDirection;
    change_percent: number | null;
  }>;
}

export interface DQRootCause {
  type: string;
  description: string;
  details: Record<string, unknown>;
  confidence: number;
}

export interface DQRootCauseAnalysis {
  dq_run_id: string;
  analysis_date: string;
  root_causes: DQRootCause[];
  primary_cause: DQRootCause | null;
  recommendations: string[];
}

export interface DQRootCauseFilters {
  dq_run_id?: string;
  asset_id?: string;
  lookback_days?: number;
}

// ─────────────────────────────────────────────────────────────────────
// Phase 240.4.A — DQAlertingRule shapes.
// Mirror the backend ``DQAlertingRule`` model + serializer.
// ─────────────────────────────────────────────────────────────────────

export const DQAlertChannel = {
  EMAIL: 'EMAIL',
  SLACK: 'SLACK',
  WEBHOOK: 'WEBHOOK',
  PAGERDUTY: 'PAGERDUTY',
} as const;
export type DQAlertChannel = (typeof DQAlertChannel)[keyof typeof DQAlertChannel];

export const DQ_ALERT_CHANNELS: readonly DQAlertChannel[] = [
  DQAlertChannel.EMAIL,
  DQAlertChannel.SLACK,
  DQAlertChannel.WEBHOOK,
  DQAlertChannel.PAGERDUTY,
] as const;

export const DQComparisonOperator = {
  LT: '<',
  LTE: '<=',
  GT: '>',
  GTE: '>=',
  EQ: '==',
  NEQ: '!=',
} as const;
export type DQComparisonOperator =
  (typeof DQComparisonOperator)[keyof typeof DQComparisonOperator];

export interface DQAlertingRule {
  id: string;
  tenant: string;
  asset?: string | null;
  name: string;
  description: string;
  metric_type: string;
  threshold: number;
  comparison_operator: DQComparisonOperator;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  alert_channels: DQAlertChannel[];
  channel_config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface DQAlertingRuleCreateRequest {
  asset_id?: string;
  name?: string;
  description?: string;
  metric_type?: string;
  threshold: number;
  comparison_operator?: DQComparisonOperator;
  severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  alert_channels?: DQAlertChannel[];
  channel_config?: Record<string, unknown>;
  enabled?: boolean;
}

export interface DQAlertingRuleUpdateRequest {
  name?: string;
  description?: string;
  threshold?: number;
  comparison_operator?: DQComparisonOperator;
  severity?: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  alert_channels?: DQAlertChannel[];
  channel_config?: Record<string, unknown>;
  enabled?: boolean;
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
