/**
 * Asset Types
 * Based on backend AssetSerializer and Asset model
 */

export const AssetStatus = {
  DRAFT: 'DRAFT',
  ACTIVE: 'ACTIVE',
  RETIRED: 'RETIRED',
} as const;
export type AssetStatus = (typeof AssetStatus)[keyof typeof AssetStatus];

export const AssetVisibility = {
  INTERNAL: 'INTERNAL',
  EXTERNAL: 'EXTERNAL',
  PUBLIC: 'PUBLIC',
} as const;
export type AssetVisibility = (typeof AssetVisibility)[keyof typeof AssetVisibility];

export const DQStatus = {
  PENDING: 'PENDING',
  PASSED: 'PASSED',
  FAILED: 'FAILED',
  WARNING: 'WARNING',
} as const;
export type DQStatus = (typeof DQStatus)[keyof typeof DQStatus];

export const ComplianceStatus = {
  PENDING: 'PENDING',
  COMPLIANT: 'COMPLIANT',
  NON_COMPLIANT: 'NON_COMPLIANT',
  WARNING: 'WARNING',
} as const;
export type ComplianceStatus = (typeof ComplianceStatus)[keyof typeof ComplianceStatus];

export interface Asset {
  id: string;
  tenant: string;
  key: string;
  name: string;
  description?: string;
  domain?: string;
  status: AssetStatus;
  visibility: AssetVisibility;
  dq_status: DQStatus;
  compliance_status: ComplianceStatus;
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  // Linked resources (populated in detail view)
  contract_id?: string;
  dataset_id?: string;
}

export interface AssetCreateRequest {
  key: string;
  name: string;
  description?: string;
  domain?: string;
  visibility?: AssetVisibility;
}

export interface AssetUpdateRequest {
  name?: string;
  description?: string;
  domain?: string;
  status?: AssetStatus;
  visibility?: AssetVisibility;
  version?: number;
}

export interface AssetListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  domain?: string;
  status?: AssetStatus;
  visibility?: AssetVisibility;
  dq_status?: string;
  compliance_status?: string;
}

export interface AttachContractRequest {
  contract_id: string;
}

export interface AttachDatasetRequest {
  dataset_id: string;
}

/** Health score response from GET /api/v1/assets/{id}/health-score/ */
export interface AssetHealthScoreResponse {
  asset_id: string;
  health_score: number | null;
  dq_status?: string;
  compliance_status?: string;
  breakdown?: AssetHealthScoreBreakdown;
  breakdown_error?: string;
}

export interface AssetHealthScoreBreakdown {
  total_score: number;
  components: {
    dq?: { score: number; weight: number; weighted_score: number; status?: string };
    compliance?: { score: number; weight: number; weighted_score: number; status?: string };
    freshness?: { score: number; weight: number; weighted_score: number };
    usage?: {
      score: number;
      weight: number;
      weighted_score: number;
      view_count?: number;
      download_count?: number;
    };
  };
}

/** Recommendation item from GET /api/v1/assets/recommendations/ */
export interface AssetRecommendation {
  asset_id: string;
  asset_name: string;
  asset_key: string;
  score: number;
  reasons: Array<{ reason: string; type: string }>;
}

export interface AssetRecommendationsFilters {
  user_id?: string;
  asset_id?: string;
  limit?: number;
  include_usage_patterns?: boolean;
  include_lineage?: boolean;
  include_user_behavior?: boolean;
}
