/**
 * Mesh Service
 * API client for mesh domain operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  MeshDomain,
  MeshDomainCreateRequest,
  MeshDomainUpdateRequest,
  MeshDomainListFilters,
  DomainAnalytics,
  MeshTopology,
  DomainTopology,
  PolicyApplication,
  ApplyPolicyRequest,
  ComplianceReport,
  CheckComplianceRequest,
} from '../../../shared/types/mesh';

const MESH_BASE_PATH = 'mesh';

export const meshService = {
  /**
   * List mesh domains with filtering and pagination
   */
  async listDomains(filters: MeshDomainListFilters = {}): Promise<PaginatedResponse<MeshDomain>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.status) params.append('status', filters.status);
    if (filters.owner_id) params.append('owner_id', filters.owner_id);

    const response = await apiClient.getClient().get<PaginatedResponse<MeshDomain>>(
      `${MESH_BASE_PATH}/domains/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get mesh domain by ID
   */
  async getDomainById(id: string): Promise<MeshDomain> {
    const response = await apiClient.getClient().get<MeshDomain>(`${MESH_BASE_PATH}/domains/${id}/`);
    return response.data;
  },

  /**
   * Create a new mesh domain
   */
  async createDomain(data: MeshDomainCreateRequest): Promise<MeshDomain> {
    const response = await apiClient.getClient().post<MeshDomain>(`${MESH_BASE_PATH}/domains/`, data);
    return response.data;
  },

  /**
   * Update a mesh domain
   */
  async updateDomain(id: string, data: MeshDomainUpdateRequest): Promise<MeshDomain> {
    const response = await apiClient.getClient().put<MeshDomain>(`${MESH_BASE_PATH}/domains/${id}/`, data);
    return response.data;
  },

  /**
   * Partially update a mesh domain
   */
  async patchDomain(id: string, data: Partial<MeshDomainUpdateRequest>): Promise<MeshDomain> {
    const response = await apiClient.getClient().patch<MeshDomain>(`${MESH_BASE_PATH}/domains/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a mesh domain
   */
  async deleteDomain(id: string): Promise<void> {
    await apiClient.getClient().delete(`${MESH_BASE_PATH}/domains/${id}/`);
  },

  /**
   * Get domain analytics
   */
  async getDomainAnalytics(id: string): Promise<DomainAnalytics> {
    const response = await apiClient.getClient().get<DomainAnalytics>(`${MESH_BASE_PATH}/domains/${id}/analytics/`);
    return response.data;
  },

  /**
   * Get mesh topology
   */
  async getTopology(includeHealthMetrics: boolean = false): Promise<MeshTopology> {
    const params = new URLSearchParams();
    if (includeHealthMetrics) {
      params.append('include_health_metrics', 'true');
    }
    const response = await apiClient.getClient().get<MeshTopology>(
      `${MESH_BASE_PATH}/topology/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get domain-specific topology
   */
  async getDomainTopology(id: string, includeHealthMetrics: boolean = true): Promise<DomainTopology> {
    const params = new URLSearchParams();
    if (includeHealthMetrics) {
      params.append('include_health_metrics', 'true');
    }
    const response = await apiClient.getClient().get<DomainTopology>(
      `${MESH_BASE_PATH}/topology/${id}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get mesh health metrics
   */
  async getMeshHealth(): Promise<unknown> {
    const response = await apiClient.getClient().get(`${MESH_BASE_PATH}/topology/health/`);
    return response.data;
  },

  /**
   * Get domain relationships
   */
  async getDomainRelationships(): Promise<unknown> {
    const response = await apiClient.getClient().get(`${MESH_BASE_PATH}/topology/relationships/`);
    return response.data;
  },

  /**
   * List policies for a domain
   */
  async listDomainPolicies(domainId: string): Promise<PolicyApplication[]> {
    const response = await apiClient.getClient().get<PolicyApplication[]>(`${MESH_BASE_PATH}/domains/${domainId}/policies/`);
    return response.data;
  },

  /**
   * Apply a policy to a domain
   */
  async applyPolicy(domainId: string, data: ApplyPolicyRequest): Promise<PolicyApplication> {
    const response = await apiClient.getClient().post<PolicyApplication>(
      `${MESH_BASE_PATH}/domains/${domainId}/policies/apply/`,
      data
    );
    return response.data;
  },

  /**
   * Remove a policy from a domain
   */
  async removePolicy(domainId: string, policyId: string): Promise<void> {
    await apiClient.getClient().delete(`${MESH_BASE_PATH}/domains/${domainId}/policies/${policyId}/`);
  },

  /**
   * Check compliance for a domain
   */
  async checkCompliance(domainId: string, data?: CheckComplianceRequest): Promise<ComplianceReport> {
    const response = await apiClient.getClient().post<ComplianceReport>(
      `${MESH_BASE_PATH}/domains/${domainId}/compliance/check/`,
      data || {}
    );
    return response.data;
  },

  /**
   * List compliance reports for a domain
   */
  async listComplianceReports(domainId: string): Promise<ComplianceReport[]> {
    const response = await apiClient.getClient().get<ComplianceReport[]>(
      `${MESH_BASE_PATH}/domains/${domainId}/compliance/reports/`
    );
    return response.data;
  },

  /**
   * Get a specific compliance report
   */
  async getComplianceReport(domainId: string, reportId: string): Promise<ComplianceReport> {
    const response = await apiClient.getClient().get<ComplianceReport>(
      `${MESH_BASE_PATH}/domains/${domainId}/compliance/reports/${reportId}/`
    );
    return response.data;
  },

  /**
   * Transfer domain ownership
   */
  async transferOwnership(domainId: string, newOwnerId: string | null): Promise<MeshDomain> {
    const response = await apiClient.getClient().post<MeshDomain>(
      `${MESH_BASE_PATH}/domains/${domainId}/transfer-ownership/`,
      { new_owner_id: newOwnerId }
    );
    return response.data;
  },
};
