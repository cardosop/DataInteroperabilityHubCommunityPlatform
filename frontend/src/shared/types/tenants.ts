/**
 * Tenant Types
 * Based on backend tenant models and serializers
 */

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  region?: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'DELETED' | 'INACTIVE';
  kyc_status: 'VERIFIED' | 'UNVERIFIED' | 'PENDING' | 'REJECTED';
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
export interface TenantUsage {
  tenant_id: string;
  asset_count: number;
  dataset_count: number;
  scheduled_ingestion_count: number;
  scheduled_export_count: number;
  storage_bytes: number;
  storage_gb: number;
  api_calls_this_month: number;
  plan_limits: Record<string, number | null>;
  usage_percentages: Record<string, number | null>;
  plan_slug?: string;
  plan_tier?: string;
}
