/**
 * Compliance Types
 * Based on backend ComplianceRunSerializer and ComplianceRun model
 */

export const ComplianceRunStatus = {
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  SUCCEEDED: 'SUCCEEDED',
  FAILED: 'FAILED',
} as const;
export type ComplianceRunStatus = (typeof ComplianceRunStatus)[keyof typeof ComplianceRunStatus];

export const ComplianceOverallStatus = {
  PASS: 'PASS',
  WARN: 'WARN',
  FAIL: 'FAIL',
} as const;
export type ComplianceOverallStatus = (typeof ComplianceOverallStatus)[keyof typeof ComplianceOverallStatus];

export const RiskLevel = {
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
  LOW: 'LOW',
  UNKNOWN: 'UNKNOWN',
} as const;
export type RiskLevel = (typeof RiskLevel)[keyof typeof RiskLevel];

export interface ComplianceColumnFinding {
  column: string;
  categories: string[];
  match_ratio: number;
  confidence?: string;
  sample_matches?: number;
  total_sampled?: number;
  /** @deprecated Use `column` instead */
  column_name?: string;
  /** @deprecated Use `categories` instead */
  pii_types?: string[];
  /** @deprecated Use `match_ratio` instead */
  risk_score?: number;
  regulations_affected?: string[];
  sample_values?: string[];
}

export interface ComplianceRun {
  id: string;
  tenant: string;
  asset?: string;
  dataset?: string;
  file?: string;
  job: string;
  regulations?: string[];
  status: ComplianceRunStatus;
  overall_status?: ComplianceOverallStatus;
  risk_level?: RiskLevel;
  allowed_to_store?: boolean;
  detected_categories_json?: Record<string, unknown>;
  column_findings_json?: ComplianceColumnFinding[];
  regulation_mapping_json?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ComplianceRunCreateRequest {
  asset_id?: string;
  dataset_id?: string;
  file_id?: string;
  scan_mode?: 'internal' | 'external';
  applicable_regulations?: string[];
}

export interface ComplianceRunListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  status?: ComplianceRunStatus;
  asset?: string;
}

export interface ComplianceRunResults {
  compliance_run_id: string;
  overall_status?: ComplianceOverallStatus;
  risk_level?: RiskLevel;
  allowed_to_store?: boolean;
  compliance_score?: number;
  score_breakdown: {
    total_columns: number;
    columns_with_pii: number;
    columns_without_pii: number;
    pii_detection_rate: number;
    base_score: number;
    pii_penalty: number;
    final_score: number;
  };
  violations: Array<{
    column: string;
    pii_type: string;
    risk_score: number;
    severity: 'HIGH' | 'MEDIUM' | 'LOW';
  }>;
  violation_details: Array<{
    column: string;
    pii_type: string;
    risk_score: number;
    severity: string;
    regulations_affected?: string[];
    detection_confidence?: number;
    sample_values?: string[];
  }>;
  remediation_suggestions: Array<{
    column: string;
    pii_type: string;
    suggestion: string;
    priority: string;
  }>;
  risk_assessment: {
    overall_risk_level: string;
    risk_score: number;
    allowed_to_store: boolean;
    total_violations: number;
    high_severity_violations: number;
    medium_severity_violations: number;
    low_severity_violations: number;
    regulations_checked: string[];
    recommendations: string[];
  };
  violation_timeline: Array<{
    timestamp: string;
    event: string;
    violations_detected: number;
    risk_level: string;
  }>;
  regulations: string[];
  detected_categories?: Record<string, unknown>;
  column_findings: ComplianceColumnFinding[];
  started_at?: string;
  completed_at?: string;
}
