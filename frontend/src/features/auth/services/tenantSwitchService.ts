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
  // 313.H.4 — defensive normalization: the callers (Header tenant
  // switcher) assume an array. A malformed payload (object instead of
  // array from schema drift or a proxy returning an error shape) used to
  // crash the Header render with "tenants.find is not a function".
  // Normalize here — the service boundary is the right place.
  return Array.isArray(response.data) ? response.data : [];
}

/** POST /auth/switch-tenant/ — switch active tenant, returns me summary */
export async function switchTenant(tenant_id: string): Promise<User> {
  const response = await apiClient
    .getClient()
    .post<User>('/auth/switch-tenant/', { tenant_id });
  return response.data;
}
