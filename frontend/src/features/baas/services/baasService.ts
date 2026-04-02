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
  CustomerBillingReport,
  BillingReportGenerateRequest,
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
  async getDocumentation(): Promise<unknown> {
    const response = await apiClient.getClient().get(`${BAAS_BASE_PATH}/docs/`);
    return response.data;
  },

  // --- Billing Reports (Phase 116C) ---

  async listBillingReports(filters: { customer_id?: string; status?: string } = {}): Promise<PaginatedResponse<CustomerBillingReport>> {
    const params = new URLSearchParams();
    if (filters.customer_id) params.append('customer_id', filters.customer_id);
    if (filters.status) params.append('status', filters.status);
    const response = await apiClient.getClient().get<PaginatedResponse<CustomerBillingReport>>(
      `${BAAS_BASE_PATH}/billing-reports/?${params.toString()}`
    );
    return response.data;
  },

  async getBillingReport(id: string): Promise<CustomerBillingReport> {
    const response = await apiClient.getClient().get<CustomerBillingReport>(
      `${BAAS_BASE_PATH}/billing-reports/${id}/`
    );
    return response.data;
  },

  async generateBillingReport(data: BillingReportGenerateRequest): Promise<CustomerBillingReport> {
    const response = await apiClient.getClient().post<CustomerBillingReport>(
      `${BAAS_BASE_PATH}/billing-reports/generate/`, data
    );
    return response.data;
  },

  async finalizeBillingReport(id: string): Promise<CustomerBillingReport> {
    const response = await apiClient.getClient().post<CustomerBillingReport>(
      `${BAAS_BASE_PATH}/billing-reports/${id}/finalize/`
    );
    return response.data;
  },

  async sendBillingReport(id: string): Promise<CustomerBillingReport> {
    const response = await apiClient.getClient().post<CustomerBillingReport>(
      `${BAAS_BASE_PATH}/billing-reports/${id}/send/`
    );
    return response.data;
  },

  async voidBillingReport(id: string, reason?: string): Promise<CustomerBillingReport> {
    const response = await apiClient.getClient().post<CustomerBillingReport>(
      `${BAAS_BASE_PATH}/billing-reports/${id}/void/`,
      reason ? { reason } : {}
    );
    return response.data;
  },

  async getInvoicePdf(reportId: string): Promise<Blob> {
    const response = await apiClient.getClient().get(
      `${BAAS_BASE_PATH}/billing-reports/${reportId}/`,
    );
    // PDF is stored as base64 in metadata_json — decode client-side
    const meta = response.data?.metadata_json || response.data;
    if (meta?.pdf_base64) {
      const binary = atob(meta.pdf_base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      return new Blob([bytes], { type: 'application/pdf' });
    }
    throw new Error('No PDF available for this report');
  },
};
