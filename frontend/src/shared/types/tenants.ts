/**
 * Tenant Types
 * Based on backend tenant models and serializers
 */

/** Backend `RiskLevel` choices (`hub/apps/compliance/models.py`).
 *  Promoted to a `const` tuple so we can derive the literal union AND
 *  validate user-controlled input (e.g. form fields) at runtime via
 *  {@link isComplianceRiskThreshold}. */
export const COMPLIANCE_RISK_THRESHOLDS = [
  'NONE',
  'LOW',
  'MEDIUM',
  'HIGH',
  'CRITICAL',
] as const;
export type ComplianceRiskThreshold =
  (typeof COMPLIANCE_RISK_THRESHOLDS)[number];

export function isComplianceRiskThreshold(
  value: unknown,
): value is ComplianceRiskThreshold {
  return (
    typeof value === 'string' &&
    (COMPLIANCE_RISK_THRESHOLDS as readonly string[]).includes(value)
  );
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  region?: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'DELETED' | 'INACTIVE';
  kyc_status: 'VERIFIED' | 'UNVERIFIED' | 'PENDING' | 'REJECTED';
  /**
   * Phase 235.3 — soft-delete grace anchor. Non-null when the tenant
   * has been deactivated via ``DELETE /api/v1/admin/tenants/{id}/``;
   * the daily cron hard-deletes the tenant 90 days after this
   * timestamp.
   */
  scheduled_for_deletion_at?: string | null;
  /**
   * Phase 235.3 — legal-hold flag. When True, blocks both the
   * Deactivate endpoint (HTTP 422 LEGAL_HOLD_ACTIVE) and the daily
   * hard-delete sweep. The SPA pre-disables the Deactivate button
   * when this is True so operators see the precondition without
   * needing to click + error.
   */
  legal_hold?: boolean;
  /**
   * Phase 235.4 — when True, PLATFORM_ADMIN may impersonate users in
   * this tenant via the admin impersonate endpoint. The SPA hides the
   * ImpersonationButton on user-detail pages when this is False
   * (mirrors the backend gate so a misconfigured FE can't trigger the
   * 403 round-trip).
   */
  impersonation_allowed?: boolean;
  /**
   * Phase 235.4 — per-tenant default for an impersonation session's
   * duration cap (minutes). Hard cap is 240 enforced server-side.
   */
  impersonation_default_max_minutes?: number;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantListFilters {
  page?: number;
  page_size?: number;
  status?: string;
}

export interface TenantConfig {
  tenant_id: string;
  default_dq_profile?: string;
  allowed_compliance_regimes?: string[];
  default_compliance_regimes?: string[];
  data_retention_days?: number;
  rate_limits?: Record<string, unknown>;
  max_file_size_bytes?: number;
  max_job_concurrency?: number;
  max_queued_jobs?: number;
  trust_signals_enabled?: boolean;
  versioning_enabled?: boolean;
  workflows_enabled?: boolean;
  compliance_risk_threshold?: ComplianceRiskThreshold;
  /**
   * Phase 270.C.4 — per-tenant compliance legal-basis strict mode.
   * When true, the compliance microservice rejects scans missing a
   * valid GDPR/UK_GDPR/LGPD ``legal_basis`` with HTTP 422
   * ``LEGAL_BASIS_INVALID``. When false (default in staging/dev),
   * the scan succeeds with an ERROR-severity issue in the report
   * (Phase 19.7.1 behaviour). Surfaced via the
   * ``Tenant.compliance_legal_basis_strict`` model field.
   */
  compliance_legal_basis_strict?: boolean;
  created_at: string;
  updated_at: string;
}

/** Partial update payload for PATCH /tenants/me/config/ */
export interface TenantConfigUpdate {
  default_dq_profile?: string | null;
  allowed_compliance_regimes?: string[];
  default_compliance_regimes?: string[];
  data_retention_days?: number | null;
  rate_limits?: Record<string, unknown> | null;
  max_file_size_bytes?: number | null;
  max_job_concurrency?: number | null;
  max_queued_jobs?: number | null;
  trust_signals_enabled?: boolean | null;
  versioning_enabled?: boolean | null;
  workflows_enabled?: boolean | null;
  compliance_risk_threshold?: ComplianceRiskThreshold | null;
  /** Phase 270.C.4 — see ``TenantConfig.compliance_legal_basis_strict``. */
  compliance_legal_basis_strict?: boolean | null;
}

/** Single tenant usage row from GET /platform/tenants/usage/ */
export interface PlatformTenantUsageRow {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  plan_slug: string | null;
  plan_tier: string | null;
  usage: {
    api_calls_count: number;
    asset_count: number;
    dataset_count: number;
    scheduled_ingestion_runs_count: number;
    scheduled_export_runs_count: number;
    storage_bytes: number;
    storage_gb: number;
  };
  plan_limits: Record<string, unknown>;
  period_start: string;
  period_end: string;
}

/** Response from GET /platform/tenants/usage/ */
export interface PlatformTenantUsageResponse {
  count: number;
  results: PlatformTenantUsageRow[];
  period_start: string;
  period_end: string;
}

/** Request for POST /tenants/onboarding/ (self-service org tenant creation) */
export interface TenantOnboardingRequest {
  name: string;
  slug: string;
  plan_slug?: string;
  first_user: {
    email: string;
    password: string;
    display_name?: string;
  };
  region?: string;
}

/** Response from POST /tenants/onboarding/ */
export interface TenantOnboardingResponse {
  tenant: { id: string; name: string; slug: string; status: string; plan?: string };
  user: { id: string; email: string; display_name?: string; status: string };
  subscription_id: string | null;
  plan: { slug: string; name: string; tier: string };
}

/** Response from GET /tenants/me/usage/ */
interface QuotaWarning {
  usage: number;
  limit: number;
  percentage: number;
}

export interface TenantUsage {
  tenant_id: string;
  storage_bytes: number;
  storage_gb: number;
  api_calls_this_month: number;
  asset_count: number;
  dataset_count: number;
  scheduled_ingestion_count: number;
  scheduled_export_count: number;
  period_start: string | null;
  period_end: string | null;
  threshold_status: string;
  overall_status: string;
  upgrade_recommendation: string[];
  /** Phase 277.B.106 — dynamic usage keys: {limit_key}_usage for every KNOWN_LIMIT_KEY */
  [key: `${string}_usage`]: number | string;
  plan_limits: Record<string, number | null>;
  usage_percentages: Record<string, number | null>;
  /** Phase 277.B.106 — any limit at >=80% flagged with {usage, limit, percentage} */
  quota_warnings: Record<string, QuotaWarning>;
  plan_slug?: string;
  plan_tier?: string;
  plan_compliance_pro_pack?: boolean;
}

export interface TenantTaxIdResponse {
  tax_id: string | null;
  tax_id_type: string | null;
  tax_id_verified: boolean;
  tax_address: string | null;
}
