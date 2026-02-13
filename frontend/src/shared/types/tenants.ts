/**
 * Tenant Types
 * Based on backend tenant models and serializers
 */

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  region?: string;
  status: 'ACTIVE' | 'SUSPENDED' | 'INACTIVE';
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
  created_at: string;
  updated_at: string;
}
