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

/**
 * Phase 250.7.A.1 — semantic-mapping + search-indexing status.
 * Mirrors the backend `SemanticStatus` enum. ``UNKNOWN`` for assets
 * created before 250.7.A shipped (we haven't checked yet) — the
 * SPA's degraded-banner code branches on `FAIL` only and renders
 * nothing for `UNKNOWN` / `PASS`.
 */
export const SemanticStatus = {
  UNKNOWN: 'UNKNOWN',
  PASS: 'PASS',
  WARN: 'WARN',
  FAIL: 'FAIL',
} as const;
export type SemanticStatus = (typeof SemanticStatus)[keyof typeof SemanticStatus];

export interface Asset {
  id: string;
  tenant: string;
  key: string;
  name: string;
  description?: string;
  domain?: string;
  status: AssetStatus;
  /**
   * Phase 250.3.B (D250.4) — `visibility` is now DERIVED from `status`
   * server-side: PUBLIC iff `status === 'PUBLIC'`, else INTERNAL. The
   * field is read-only on the wire (the backend ignores it on writes
   * during phase-1 and rejects it during phase-2). Treat as
   * `Readonly<AssetVisibility>` in UI code.
   */
  readonly visibility: AssetVisibility;
  dq_status: DQStatus;
  compliance_status: ComplianceStatus;
  /**
   * Phase 250.7.A.1 — post-activation semantic / search status.
   * Surfaced for the SPA's `<SemanticDegradedBanner>` to render
   * "active but not yet discoverable" when `FAIL`. Optional on
   * the type so list-view payloads (which may omit it) still
   * type-check.
   */
  semantic_status?: SemanticStatus;
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  // Linked resources (populated in detail view)
  contract_id?: string;
  dataset_id?: string;
  // Phase 230 (REQ-SEM-DISCO-001 / 230.1.2) — canonical IRI
  // emitted by hub/apps/assets/serializers.py:33. Optional on the
  // type so list-view payloads (which may omit it) still type-check.
  canonical_iri?: string;
}

export interface AssetCreateRequest {
  key: string;
  name: string;
  description?: string;
  domain?: string;
  /**
   * @deprecated Phase 250.3.B (D250.4) — visibility derives from
   * status server-side. The field is silently ignored in phase-1
   * and removed in phase-2. New code should set `status` instead.
   */
  visibility?: AssetVisibility;
}

export interface AssetUpdateRequest {
  name?: string;
  description?: string;
  domain?: string;
  status?: AssetStatus;
  /**
   * @deprecated Phase 250.3.B (D250.4) — see `AssetCreateRequest.visibility`.
   * Setting visibility on PATCH is a no-op in phase-1 and a
   * `400 FIELD_REMOVED` rejection once phase-2 ships.
   */
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
  /** 223.2 — filter assets that are linked to a specific contract. */
  contract_id?: string;
}

/**
 * Phase 250.6.C — wire shape for the asset workflow-status endpoint
 * (`GET /api/v1/assets/workflows/{workflow_instance_id}/status/`),
 * polled by `useAssetWorkflowStatus` to drive the
 * `<WorkflowProgressWidget>` on the asset detail page.
 *
 * Mirrors the backend response shape at
 * `hub/apps/assets/views.py::get_asset_workflow_status`.
 */
export interface AssetWorkflowStatus {
  workflow_instance_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  progress_percentage: number;
  current_step_name: string | null;
  /** Set on COMPLETED + any RUNNING after the create_asset_record step. */
  asset_id: string | null;
  message: string;
  /** ISO-8601 timestamp; the FE uses this to apply F2-4 polling
   *  backoff (1.5s → 5s → 15s after 30s of RUNNING). Null on rare
   *  edge cases where the workflow row has no created_at. */
  started_at: string | null;
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
