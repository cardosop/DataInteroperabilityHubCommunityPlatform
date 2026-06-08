/**
 * Tenant Service
 * API client for tenant usage, config (me endpoints), and onboarding
 * GET /api/v1/tenants/me/usage/
 * GET/PATCH /api/v1/tenants/me/config/
 * POST /api/v1/tenants/onboarding/ (self-service org tenant creation, no auth)
 */

import { apiClient } from '../../../shared/api/client';
import type {
  TenantConfig,
  TenantConfigUpdate,
  TenantOnboardingRequest,
  TenantOnboardingResponse,
  TenantTaxIdResponse,
  TenantUsage,
} from '../../../shared/types/tenants';

const TENANTS_BASE = 'tenants';

export const tenantService = {
  /**
   * Create organization tenant with first user (self-service, no auth required).
   * POST /api/v1/tenants/onboarding/
   */
  async createOrgTenant(data: TenantOnboardingRequest): Promise<TenantOnboardingResponse> {
    // Extended timeout: onboarding creates tenant + user + subscription + roles in a single
    // transaction.  Under load this can exceed the default 30s Axios timeout.
    const response = await apiClient
      .getClient()
      .post<TenantOnboardingResponse>(`${TENANTS_BASE}/onboarding/`, data, { timeout: 90000 });
    return response.data;
  },

  /**
   * Get current tenant usage (storage, API calls, limits)
   */
  async getMeUsage(): Promise<TenantUsage> {
    const response = await apiClient
      .getClient()
      .get<TenantUsage>(`${TENANTS_BASE}/me/usage/`);
    return response.data;
  },

  /**
   * Get current tenant configuration
   */
  async getMeConfig(): Promise<TenantConfig> {
    const response = await apiClient
      .getClient()
      .get<TenantConfig>(`${TENANTS_BASE}/me/config/`);
    return response.data;
  },

  /**
   * Update current tenant configuration (partial)
   */
  async patchMeConfig(payload: TenantConfigUpdate): Promise<TenantConfig> {
    const response = await apiClient
      .getClient()
      .patch<TenantConfig>(`${TENANTS_BASE}/me/config/`, payload);
    return response.data;
  },

  /**
   * Get current tenant tax ID info.
   * GET /api/v1/tenants/me/tax-id/
   */
  async getMeTaxId(): Promise<TenantTaxIdResponse> {
    const response = await apiClient
      .getClient()
      .get<TenantTaxIdResponse>(`${TENANTS_BASE}/me/tax-id/`);
    return response.data;
  },

  /**
   * Set or update current tenant tax ID info.
   * POST /api/v1/tenants/me/tax-id/
   */
  async postMeTaxId(data: {
    tax_id: string;
    tax_id_type: string;
    tax_address?: { country?: string; postal_code?: string; line1?: string };
  }): Promise<TenantTaxIdResponse> {
    const response = await apiClient
      .getClient()
      .post<TenantTaxIdResponse>(`${TENANTS_BASE}/me/tax-id/`, data);
    return response.data;
  },

  // ---------------------------------------------------------------------
  // Phase 230.8 (REQ-SEM-FED-001) — SPARQL federation allowlist CRUD
  // ---------------------------------------------------------------------

  /**
   * List the active SPARQL federation allowlist for a tenant.
   */
  async listSparqlEndpoints(tenantId: string): Promise<SparqlEndpoint[]> {
    const response = await apiClient
      .getClient()
      .get<SparqlEndpointListResponse>(`${TENANTS_BASE}/${tenantId}/sparql-endpoints/`);
    const body = response.data as unknown;
    if (Array.isArray(body)) return body as SparqlEndpoint[];
    return (body as { results?: SparqlEndpoint[] }).results ?? [];
  },

  /**
   * Add a SPARQL endpoint to the tenant allowlist.  The Hub validates
   * SSRF policy before persisting; on rejection the response carries
   * a stable ``code`` field (``SSRF_TARGET_BLOCKED`` / ``INVALID_URL_SCHEME``).
   */
  async createSparqlEndpoint(
    tenantId: string,
    payload: { name: string; endpoint_url: string; is_active?: boolean },
  ): Promise<SparqlEndpoint> {
    const response = await apiClient
      .getClient()
      .post<SparqlEndpoint>(`${TENANTS_BASE}/${tenantId}/sparql-endpoints/`, payload);
    return response.data;
  },

  /**
   * Update an allowlist row (typically used to flip ``is_active``).
   */
  async patchSparqlEndpoint(
    tenantId: string,
    endpointId: string,
    payload: Partial<{ name: string; endpoint_url: string; is_active: boolean }>,
  ): Promise<SparqlEndpoint> {
    const response = await apiClient
      .getClient()
      .patch<SparqlEndpoint>(
        `${TENANTS_BASE}/${tenantId}/sparql-endpoints/${endpointId}/`,
        payload,
      );
    return response.data;
  },

  /**
   * Remove an allowlist row (audit-logged on the server).
   */
  async deleteSparqlEndpoint(tenantId: string, endpointId: string): Promise<void> {
    await apiClient
      .getClient()
      .delete(`${TENANTS_BASE}/${tenantId}/sparql-endpoints/${endpointId}/`);
  },

  // --------------------------------------------------------------------
  // Phase 250.6.E — per-tenant feature-flags admin surface
  // --------------------------------------------------------------------

  /**
   * Get the per-tenant feature-flags (current values + descriptions).
   * GET /api/v1/tenants/me/feature-flags/
   * TENANT_ADMIN-only on the backend.
   */
  async getMeFeatureFlags(): Promise<TenantFeatureFlagsResponse> {
    const response = await apiClient
      .getClient()
      .get<TenantFeatureFlagsResponse>(`${TENANTS_BASE}/me/feature-flags/`);
    return response.data;
  },

  /**
   * Patch one or more per-tenant feature flags.
   * PATCH /api/v1/tenants/me/feature-flags/
   * Each flipped flag emits a TENANT_FEATURE_FLAG_UPDATED audit row.
   */
  async patchMeFeatureFlags(
    payload: Record<string, boolean>,
  ): Promise<TenantFeatureFlagsResponse> {
    const response = await apiClient
      .getClient()
      .patch<TenantFeatureFlagsResponse>(
        `${TENANTS_BASE}/me/feature-flags/`,
        payload,
      );
    return response.data;
  },

  /**
   * Get the audit-log history of feature-flag changes for the
   * current tenant.
   * GET /api/v1/tenants/me/feature-flag-history/
   */
  async getMeFeatureFlagHistory(): Promise<TenantFeatureFlagHistoryResponse> {
    const response = await apiClient
      .getClient()
      .get<TenantFeatureFlagHistoryResponse>(
        `${TENANTS_BASE}/me/feature-flag-history/`,
      );
    return response.data;
  },
};

export interface TenantFeatureFlag {
  name: string;
  value: boolean;
  description: string;
}

export interface TenantFeatureFlagsResponse {
  flags: TenantFeatureFlag[];
}

export interface TenantFeatureFlagHistoryEvent {
  id: string;
  action: string;
  actor_user_id: string | null;
  result: string;
  created_at: string;
  details_json: {
    flag_name?: string;
    previous_value?: boolean;
    new_value?: boolean;
    actor_user_id?: string;
    tenant_id?: string;
    [key: string]: unknown;
  };
}

export interface TenantFeatureFlagHistoryResponse {
  events: TenantFeatureFlagHistoryEvent[];
}

export interface SparqlEndpoint {
  id: string;
  name: string;
  endpoint_url: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

interface SparqlEndpointListResponse {
  results?: SparqlEndpoint[];
}
