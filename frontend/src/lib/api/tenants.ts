/**
 * Tenant API Service
 *
 * API functions for tenant management operations:
 * - Get current tenant
 * - List all tenants (platform admin only)
 * - Get tenant by ID
 * - Update tenant
 * - Suspend/activate tenant
 * - Get tenant configuration
 * - Update tenant configuration
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Tenant status enum
 */
export type TenantStatus = 'ACTIVE' | 'SUSPENDED' | 'DELETED'

/**
 * KYC status enum
 */
export type KYCStatus = 'UNVERIFIED' | 'VERIFIED'

/**
 * Tenant model
 */
export interface Tenant {
  id: string
  name: string
  slug: string
  status: TenantStatus
  kyc_status: KYCStatus
  region?: string | null
  deleted_at?: string | null
  created_at: string
  updated_at: string
}

/**
 * Update tenant request payload
 */
export interface UpdateTenantRequest {
  name?: string
  slug?: string
  kyc_status?: KYCStatus
  region?: string | null
}

/**
 * Tenant configuration model
 */
export interface TenantConfig {
  tenant_id: string
  default_dq_profile?: string | null
  allowed_compliance_regimes?: string[]
  default_compliance_regimes?: string[]
  data_retention_days?: number | null
  rate_limits?: Record<string, {
    burst_per_10s?: number
    sustained_per_min?: number
    daily_cap?: number
  }>
  max_file_size_bytes?: number | null
  max_job_concurrency?: number | null
  max_queued_jobs?: number | null
  created_at: string
  updated_at: string
}

/**
 * Update tenant configuration request payload
 */
export interface UpdateTenantConfigRequest {
  default_dq_profile?: string | null
  allowed_compliance_regimes?: string[]
  default_compliance_regimes?: string[]
  data_retention_days?: number | null
  rate_limits?: Record<string, {
    burst_per_10s?: number
    sustained_per_min?: number
    daily_cap?: number
  }>
  max_file_size_bytes?: number | null
  max_job_concurrency?: number | null
  max_queued_jobs?: number | null
}

/**
 * List tenants query parameters
 */
export interface ListTenantsParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 50, max: 100)
   */
  page_size?: number
  /**
   * Sort fields (comma-separated, prefix with `-` for descending)
   * Example: "name,-created_at"
   */
  ordering?: string
  /**
   * Search in name, slug
   */
  search?: string
  /**
   * Filter by status (ACTIVE, SUSPENDED, DELETED)
   */
  status?: TenantStatus
  /**
   * Filter by KYC status (UNVERIFIED, VERIFIED)
   */
  kyc_status?: KYCStatus
  /**
   * Filter by region
   */
  region?: string
}

/**
 * List tenants response
 */
export interface ListTenantsResponse extends PaginatedResponse<Tenant> {}

/**
 * Suspend tenant request payload
 */
export interface SuspendTenantRequest {
  reason?: string
}

/**
 * Reactivate tenant request payload
 */
export interface ReactivateTenantRequest {
  reason?: string
}

/**
 * List all tenants (platform admin only)
 *
 * @param params - Query parameters for filtering and pagination
 * @param config - Optional Axios request config
 * @returns Paginated list of tenants
 */
export async function listTenants(
  params?: ListTenantsParams,
  config?: ExtendedFetchRequestInit
): Promise<ListTenantsResponse> {
  const response = await apiClient.get<ListTenantsResponse>('/api/v1/tenants/tenants/', {
    ...config,
    params,
  })
  return response.data
}

/**
 * Get current tenant
 * Note: This uses the tenant_id from the current user's context.
 * If tenant_id is not available, this will fail.
 *
 * @param tenantId - Tenant UUID from current user context
 * @param config - Optional Axios request config
 * @returns Current tenant details
 */
export async function getCurrentTenant(tenantId: string, config?: ExtendedFetchRequestInit): Promise<Tenant> {
  return await getTenant(tenantId, config)
}

/**
 * Get tenant by ID
 *
 * @param id - Tenant UUID
 * @param config - Optional Axios request config
 * @returns Tenant details
 */
export async function getTenant(id: string, config?: ExtendedFetchRequestInit): Promise<Tenant> {
  const response = await apiClient.get<Tenant>(`/api/v1/tenants/${id}/`, config)
  return response.data
}

/**
 * Update tenant
 *
 * @param id - Tenant UUID
 * @param data - Tenant update data
 * @param requestConfig - Optional Axios request config
 * @returns Updated tenant
 */
export async function updateTenant(
  id: string,
  data: UpdateTenantRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Tenant> {
  const response = await apiClient.patch<Tenant>(`/api/v1/tenants/${id}/`, data, requestConfig)
  return response.data
}

/**
 * Get tenant configuration
 *
 * @param tenantId - Tenant UUID
 * @param config - Optional Axios request config
 * @returns Tenant configuration
 */
export async function getTenantConfig(
  tenantId: string,
  config?: ExtendedFetchRequestInit
): Promise<TenantConfig> {
  const response = await apiClient.get<TenantConfig>(`/api/v1/tenants/${tenantId}/config/`, config)
  return response.data
}

/**
 * Update tenant configuration
 *
 * @param tenantId - Tenant UUID
 * @param data - Configuration update data
 * @param requestConfig - Optional Axios request config
 * @returns Updated tenant configuration
 */
export async function updateTenantConfig(
  tenantId: string,
  data: UpdateTenantConfigRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<TenantConfig> {
  const response = await apiClient.patch<TenantConfig>(
    `/api/v1/tenants/${tenantId}/config/`,
    data,
    requestConfig
  )
  return response.data
}

/**
 * Suspend a tenant (platform admin only)
 *
 * @param tenantId - Tenant UUID
 * @param data - Suspend request data
 * @param requestConfig - Optional Axios request config
 * @returns Updated tenant
 */
export async function suspendTenant(
  tenantId: string,
  data?: SuspendTenantRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Tenant> {
  const response = await apiClient.post<Tenant>(
    `/api/v1/tenants/tenants/${tenantId}/suspend/`,
    data || {},
    requestConfig
  )
  return response.data
}

/**
 * Reactivate a suspended tenant (platform admin only)
 *
 * @param tenantId - Tenant UUID
 * @param data - Reactivate request data
 * @param requestConfig - Optional Axios request config
 * @returns Updated tenant
 */
export async function reactivateTenant(
  tenantId: string,
  data?: ReactivateTenantRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Tenant> {
  const response = await apiClient.post<Tenant>(
    `/api/v1/tenants/tenants/${tenantId}/reactivate/`,
    data || {},
    requestConfig
  )
  return response.data
}

