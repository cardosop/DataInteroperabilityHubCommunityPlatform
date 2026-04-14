/**
 * Governance Service
 * API client for access request operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  AccessRequest,
  AccessRequestCreateRequest,
  AccessRequestListFilters,
} from '../../../shared/types/governance';

const GOVERNANCE_ACCESS_REQUESTS_PATH = 'governance/access-requests';

/** Backend returns count, page, page_size, total_pages, next, previous, results */
export interface AccessRequestListResponse {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: AccessRequest[];
}

export const governanceService = {
  /**
   * List access requests (tenant-scoped)
   */
  async list(filters: AccessRequestListFilters = {}): Promise<AccessRequestListResponse> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    if (filters.status) params.set('status', filters.status);
    if (filters.asset_id) params.set('asset_id', filters.asset_id);
    if (filters.dataset_id) params.set('dataset_id', filters.dataset_id);
    const qs = params.toString();
    const url = qs
      ? `${GOVERNANCE_ACCESS_REQUESTS_PATH}/?${qs}`
      : `${GOVERNANCE_ACCESS_REQUESTS_PATH}/`;
    const response = await apiClient.getClient().get<AccessRequestListResponse>(url);
    return response.data;
  },

  /**
   * Get access request by ID
   */
  async getById(id: string): Promise<AccessRequest> {
    const response = await apiClient
      .getClient()
      .get<AccessRequest>(`${GOVERNANCE_ACCESS_REQUESTS_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create access request
   */
  async create(data: AccessRequestCreateRequest): Promise<AccessRequest> {
    const response = await apiClient
      .getClient()
      .post<AccessRequest>(`${GOVERNANCE_ACCESS_REQUESTS_PATH}/`, data);
    return response.data;
  },

  /**
   * Approve access request (TENANT_ADMIN or in approvers list; backend enforces)
   */
  async approve(id: string, body?: { comments?: string }): Promise<AccessRequest> {
    const response = await apiClient
      .getClient()
      .post<AccessRequest>(`${GOVERNANCE_ACCESS_REQUESTS_PATH}/${id}/approve/`, body ?? {});
    return response.data;
  },

  /**
   * Reject access request (reason required)
   */
  async reject(id: string, reason: string): Promise<AccessRequest> {
    const response = await apiClient
      .getClient()
      .post<AccessRequest>(`${GOVERNANCE_ACCESS_REQUESTS_PATH}/${id}/reject/`, { reason });
    return response.data;
  },

  /**
   * Revoke an approved access request (and its marketplace entitlement)
   */
  async revoke(id: string): Promise<AccessRequest> {
    const response = await apiClient
      .getClient()
      .post<AccessRequest>(`${GOVERNANCE_ACCESS_REQUESTS_PATH}/${id}/revoke/`, {});
    return response.data;
  },
};
