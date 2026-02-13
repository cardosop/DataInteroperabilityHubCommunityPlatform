/**
 * BaaS Service
 * API client for BaaS platform operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  APIKey,
  APIKeyCreateRequest,
  APIKeyUpdateRequest,
  UsageStats,
  UsageByEndpoint,
  UsageByTenant,
  UsageFilters,
} from '../../../shared/types/baas';

const BAAS_BASE_PATH = 'baas';

export const baasService = {
  /**
   * List API keys
   */
  async listAPIKeys(filters: { tier?: string; active_only?: boolean } = {}): Promise<PaginatedResponse<APIKey>> {
    const params = new URLSearchParams();
    if (filters.tier) params.append('tier', filters.tier);
    if (filters.active_only) params.append('active_only', 'true');

    const response = await apiClient.getClient().get<PaginatedResponse<APIKey>>(
      `${BAAS_BASE_PATH}/api-keys/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get API key by ID
   */
  async getAPIKey(id: string): Promise<APIKey> {
    const response = await apiClient.getClient().get<APIKey>(`${BAAS_BASE_PATH}/api-keys/${id}/`);
    return response.data;
  },

  /**
   * Create API key
   */
  async createAPIKey(data: APIKeyCreateRequest): Promise<APIKey> {
    const response = await apiClient.getClient().post<APIKey>(`${BAAS_BASE_PATH}/api-keys/`, data);
    return response.data;
  },

  /**
   * Update API key
   */
  async updateAPIKey(id: string, data: APIKeyUpdateRequest): Promise<APIKey> {
    const response = await apiClient.getClient().patch<APIKey>(`${BAAS_BASE_PATH}/api-keys/${id}/`, data);
    return response.data;
  },

  /**
   * Revoke API key
   */
  async revokeAPIKey(id: string): Promise<void> {
    await apiClient.getClient().delete(`${BAAS_BASE_PATH}/api-keys/${id}/`);
  },

  /**
   * Get usage statistics
   */
  async getUsageStats(filters: UsageFilters = {}): Promise<UsageStats> {
    const params = new URLSearchParams();
    if (filters.api_key_id) params.append('api_key_id', filters.api_key_id);
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    const response = await apiClient.getClient().get<UsageStats>(
      `${BAAS_BASE_PATH}/usage/stats/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get usage by endpoint
   */
  async getUsageByEndpoint(filters: UsageFilters = {}): Promise<UsageByEndpoint[]> {
    const params = new URLSearchParams();
    if (filters.api_key_id) params.append('api_key_id', filters.api_key_id);
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    const response = await apiClient.getClient().get<UsageByEndpoint[]>(
      `${BAAS_BASE_PATH}/usage/by-endpoint/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get usage by tenant
   */
  async getUsageByTenant(filters: UsageFilters = {}): Promise<UsageByTenant[]> {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);

    const response = await apiClient.getClient().get<UsageByTenant[]>(
      `${BAAS_BASE_PATH}/usage/by-tenant/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get API documentation
   */
  async getDocumentation(): Promise<any> {
    const response = await apiClient.getClient().get(`${BAAS_BASE_PATH}/docs/`);
    return response.data;
  },
};
