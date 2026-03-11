/**
 * Tenant Switch Service
 * Handles listing user tenants and switching active tenant context
 */

import { apiClient } from '../../../shared/api/client';
import type { TenantSummary } from '../types/tenantSwitch';
import type { User } from '../../../shared/types/auth';

/** GET /auth/me/tenants/ — list tenants the user has membership in */
export async function getMyTenants(): Promise<TenantSummary[]> {
  const response = await apiClient.getClient().get<TenantSummary[]>('/auth/me/tenants/');
  return response.data;
}

/** POST /auth/switch-tenant/ — switch active tenant, returns me summary */
export async function switchTenant(tenant_id: string): Promise<User> {
  const response = await apiClient
    .getClient()
    .post<User>('/auth/switch-tenant/', { tenant_id });
  return response.data;
}
