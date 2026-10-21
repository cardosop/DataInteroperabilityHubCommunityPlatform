/**
 * Tenant Switch Types
 * Types for GET /auth/me/tenants/ and POST /auth/switch-tenant/
 */

/** Tenant summary from GET /auth/me/tenants/ */
export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
}

/** Request body for POST /auth/switch-tenant/ */
export interface SwitchTenantRequest {
  tenant_id: string;
}
