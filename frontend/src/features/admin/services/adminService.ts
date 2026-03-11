/**
 * Admin Service
 * API client for admin operations (tenants, users)
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  PlatformTenantUsageResponse,
  Tenant,
  TenantConfig,
  TenantListFilters,
} from '../../../shared/types/tenants';
import type { User, UserListFilters } from '../../../shared/types/users';

const TENANTS_BASE_PATH = 'tenants';
const PLATFORM_TENANTS_BASE_PATH = 'platform/tenants';
const USERS_BASE_PATH = 'users';

export const adminService = {
  /**
   * List tenants (Platform Admin only)
   */
  async listTenants(filters: TenantListFilters = {}): Promise<PaginatedResponse<Tenant>> {
    const params = new URLSearchParams();
    if (filters.page) params.set('page', String(filters.page));
    if (filters.page_size) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const url = qs ? `${TENANTS_BASE_PATH}/?${qs}` : `${TENANTS_BASE_PATH}/`;
    const response = await apiClient.getClient().get<PaginatedResponse<Tenant>>(url);
    return response.data;
  },

  /**
   * Get tenant by ID
   */
  async getTenant(id: string): Promise<Tenant> {
    const response = await apiClient.getClient().get<Tenant>(`${TENANTS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Suspend a tenant (Platform Admin only).
   * POST /api/v1/tenants/{id}/suspend/
   */
  async suspendTenant(id: string, reason?: string): Promise<Tenant> {
    const response = await apiClient.getClient().post<Tenant>(
      `${TENANTS_BASE_PATH}/${id}/suspend/`,
      reason != null ? { reason } : {}
    );
    return response.data;
  },

  /**
   * Resume (reactivate) a suspended tenant (Platform Admin only).
   * POST /api/v1/tenants/{id}/reactivate/
   */
  async resumeTenant(id: string): Promise<Tenant> {
    const response = await apiClient.getClient().post<Tenant>(
      `${TENANTS_BASE_PATH}/${id}/reactivate/`,
      {}
    );
    return response.data;
  },

  /**
   * Get usage summary for all tenants (Platform Admin only).
   * GET /api/v1/platform/tenants/usage/
   */
  async getPlatformTenantUsage(): Promise<PlatformTenantUsageResponse> {
    const response = await apiClient
      .getClient()
      .get<PlatformTenantUsageResponse>(`${PLATFORM_TENANTS_BASE_PATH}/usage/`);
    return response.data;
  },

  /**
   * Get tenant configuration
   */
  async getTenantConfig(tenantId: string): Promise<TenantConfig> {
    const response = await apiClient
      .getClient()
      .get<TenantConfig>(`${TENANTS_BASE_PATH}/${tenantId}/config/`);
    return response.data;
  },

  /**
   * List users (tenant-scoped or all for platform admin)
   */
  async listUsers(filters: UserListFilters = {}): Promise<PaginatedResponse<User>> {
    const params = new URLSearchParams();
    if (filters.page) params.set('page', String(filters.page));
    if (filters.page_size) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    const qs = params.toString();
    const url = qs ? `${USERS_BASE_PATH}/?${qs}` : `${USERS_BASE_PATH}/`;
    const response = await apiClient.getClient().get<PaginatedResponse<User>>(url);
    return response.data;
  },

  /**
   * Get user by ID
   */
  async getUser(id: string): Promise<User> {
    const response = await apiClient.getClient().get<User>(`${USERS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Update user (roles, status, display_name). Requires TENANT_ADMIN or PLATFORM_ADMIN.
   */
  async updateUser(
    id: string,
    data: { display_name?: string; status?: string; role_ids?: string[] }
  ): Promise<User> {
    const response = await apiClient.getClient().put<User>(`${USERS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * List roles (tenant-scoped or all for platform admin)
   */
  async listRoles(): Promise<{ id: string; tenant: string; name: string; description?: string }[]> {
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<{ id: string; tenant: string; name: string; description?: string }>>(
        `${USERS_BASE_PATH}/roles/?page_size=100`
      );
    return response.data.results ?? [];
  },
};
