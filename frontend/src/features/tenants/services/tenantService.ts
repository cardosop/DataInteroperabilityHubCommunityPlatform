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
};
