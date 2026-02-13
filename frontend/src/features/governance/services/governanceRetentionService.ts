/**
 * Governance Retention Service
 * API client for retention policy operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  RetentionPolicy,
  RetentionPolicyCreateRequest,
  RetentionPolicyListFilters,
  RetentionPolicyUpdateRequest,
} from '../../../shared/types/governanceRetention';

const GOVERNANCE_RETENTION_POLICIES_PATH = 'governance/retention-policies';

/** Backend returns count, page, page_size, total_pages, next, previous, results */
export interface RetentionPolicyListResponse {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: RetentionPolicy[];
}

export const governanceRetentionService = {
  /**
   * List retention policies (tenant-scoped)
   */
  async listPolicies(
    filters: RetentionPolicyListFilters = {}
  ): Promise<RetentionPolicyListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    if (filters.asset_id) params.set('asset_id', filters.asset_id);
    if (filters.dataset_id) params.set('dataset_id', filters.dataset_id);
    if (filters.file_id) params.set('file_id', filters.file_id);
    if (filters.enabled !== undefined) params.set('enabled', String(filters.enabled));
    const qs = params.toString();
    const url = qs
      ? `${GOVERNANCE_RETENTION_POLICIES_PATH}/?${qs}`
      : `${GOVERNANCE_RETENTION_POLICIES_PATH}/`;
    const response = await apiClient.getClient().get<RetentionPolicyListResponse>(url);
    return response.data;
  },

  /**
   * Get retention policy by ID
   */
  async getPolicy(id: string): Promise<RetentionPolicy> {
    const response = await apiClient
      .getClient()
      .get<RetentionPolicy>(`${GOVERNANCE_RETENTION_POLICIES_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create retention policy
   */
  async createPolicy(data: RetentionPolicyCreateRequest): Promise<RetentionPolicy> {
    const response = await apiClient
      .getClient()
      .post<RetentionPolicy>(`${GOVERNANCE_RETENTION_POLICIES_PATH}/`, data);
    return response.data;
  },

  /**
   * Update retention policy
   */
  async updatePolicy(data: RetentionPolicyUpdateRequest): Promise<RetentionPolicy> {
    const { id, ...updateData } = data;
    const response = await apiClient
      .getClient()
      .patch<RetentionPolicy>(`${GOVERNANCE_RETENTION_POLICIES_PATH}/${id}/`, updateData);
    return response.data;
  },

  /**
   * Delete retention policy
   */
  async deletePolicy(id: string): Promise<void> {
    await apiClient.getClient().delete(`${GOVERNANCE_RETENTION_POLICIES_PATH}/${id}/`);
  },
};
