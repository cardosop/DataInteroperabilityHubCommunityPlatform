/**
 * Compliance Service
 * API client for compliance run operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  ComplianceRun,
  ComplianceRunCreateRequest,
  ComplianceRunListFilters,
  ComplianceRunResults,
} from '../../../shared/types/compliance';

const COMPLIANCE_BASE_PATH = 'compliance/runs';

export const complianceService = {
  /**
   * List compliance runs with filtering and pagination
   */
  async list(filters: ComplianceRunListFilters = {}): Promise<PaginatedResponse<ComplianceRun>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.status) params.append('status', filters.status);
    if (filters.asset) params.append('asset', filters.asset);

    const response = await apiClient.getClient().get<PaginatedResponse<ComplianceRun>>(
      `${COMPLIANCE_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get compliance run by ID
   */
  async getById(id: string): Promise<ComplianceRun> {
    const response = await apiClient.getClient().get<ComplianceRun>(
      `${COMPLIANCE_BASE_PATH}/${id}/`
    );
    return response.data;
  },

  /**
   * Create a new compliance run
   */
  async create(data: ComplianceRunCreateRequest): Promise<ComplianceRun> {
    const response = await apiClient.getClient().post<ComplianceRun>(
      `${COMPLIANCE_BASE_PATH}/`,
      data
    );
    return response.data;
  },

  /**
   * Get compliance run results
   */
  async getResults(id: string): Promise<ComplianceRunResults> {
    const response = await apiClient.getClient().get<ComplianceRunResults>(
      `${COMPLIANCE_BASE_PATH}/${id}/results/`
    );
    return response.data;
  },
};
