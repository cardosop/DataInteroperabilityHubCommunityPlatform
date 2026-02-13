/**
 * Admin Service
 * API client for admin operations (tenants, users)
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type { Tenant, TenantConfig, TenantListFilters } from '../../../shared/types/tenants';
import type { User, UserListFilters } from '../../../shared/types/users';

const TENANTS_BASE_PATH = 'tenants';
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
};
