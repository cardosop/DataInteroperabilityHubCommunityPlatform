/**
 * Contract Service
 * API client for contract operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Contract,
  ContractCreateRequest,
  ContractUpdateRequest,
  ContractListFilters,
  ContractValidationResult,
  ContractLintResult,
  ContractConvertRequest,
  ContractConvertResult,
  DraftValidationResult,
} from '../../../shared/types/contracts';
import type {
  ContractLineageVisualization,
  ContractLineageVisualizationParams,
} from '../../../shared/types/lineage';
import type {
  ODPSProductCreateRequest,
  ODPSProductCreateResponse,
  ODPSWorkflowStatus,
  ODPSLinkRequest,
  ODPSLinkResponse,
  ODPSLinks,
  ODPSExportParams,
} from '../../../shared/types/odps';

const CONTRACTS_BASE_PATH = 'contracts';

export const contractService = {
  /**
   * List contracts with filtering and pagination
   */
  async list(filters: ContractListFilters = {}): Promise<PaginatedResponse<Contract>> {
    const params = new URLSearchParams();
    
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.search) params.append('search', filters.search);
    if (filters.owner_email) params.append('owner_email', filters.owner_email);
    if (filters.owner_name) params.append('owner_name', filters.owner_name);
    if (filters.tag) params.append('tag', filters.tag);
    if (filters.quality_profile) params.append('quality_profile', filters.quality_profile);
    if (filters.compliance_regime) params.append('compliance_regime', filters.compliance_regime);
    if (filters.asset_id) params.append('asset_id', filters.asset_id);
    if (filters.spec_type) params.append('spec_type', filters.spec_type);

    const response = await apiClient.getClient().get<PaginatedResponse<Contract>>(
      `${CONTRACTS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
    return response.data;
  },

  /**
   * Get contract by ID
   */
  async getById(id: string): Promise<Contract> {
    const response = await apiClient.getClient().get<Contract>(`${CONTRACTS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new contract
   */
  async create(data: ContractCreateRequest): Promise<Contract> {
    const response = await apiClient.getClient().post<Contract>(`${CONTRACTS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Update a contract
   */
  async update(id: string, data: ContractUpdateRequest): Promise<Contract> {
    const response = await apiClient.getClient().put<Contract>(`${CONTRACTS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  /**
   * Delete a contract
   */
  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${CONTRACTS_BASE_PATH}/${id}/`);
  },

  /**
   * Validate a contract draft without persisting (Phase 219.4).
   * Dry-run normalization — returns spec detection and errors/warnings.
   */
  async validateDraft(data: {
    original_raw: string;
    original_format: string;
  }): Promise<DraftValidationResult> {
    const response = await apiClient
      .getClient()
      .post<DraftValidationResult>(
        `${CONTRACTS_BASE_PATH}/validate-draft/`,
        data,
      );
    return response.data;
  },

  /**
   * Validate a contract
   */
  async validate(id: string): Promise<ContractValidationResult> {
    const response = await apiClient.getClient().post<ContractValidationResult>(
      `${CONTRACTS_BASE_PATH}/${id}/validate/`
    );
    return response.data;
  },

  /**
   * Lint a contract
   */
  async lint(id: string): Promise<ContractLintResult> {
    const response = await apiClient.getClient().post<ContractLintResult>(
      `${CONTRACTS_BASE_PATH}/${id}/lint/`
    );
    return response.data;
  },

  /**
   * Convert a contract format
   */
  async convert(id: string, data: ContractConvertRequest): Promise<ContractConvertResult> {
    const response = await apiClient.getClient().post<ContractConvertResult>(
      `${CONTRACTS_BASE_PATH}/${id}/convert/`,
      data
    );
    return response.data;
  },

  /**
   * Export a contract
   */
  async export(id: string, format?: string): Promise<Blob> {
    const url = format
      ? `${CONTRACTS_BASE_PATH}/${id}/export/?format=${format}`
      : `${CONTRACTS_BASE_PATH}/${id}/export/`;
    
    const response = await apiClient.getClient().get<Blob>(url, {
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Download a contract
   */
  async download(id: string, format?: string): Promise<Blob> {
    const url = format
      ? `${CONTRACTS_BASE_PATH}/${id}/download/?format=${format}`
      : `${CONTRACTS_BASE_PATH}/${id}/download/`;
    
    const response = await apiClient.getClient().get<Blob>(url, {
      responseType: 'blob',
    });
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // ODPS-specific operations (merged from odpsService.ts)
  // ---------------------------------------------------------------------------

  /**
   * Create ODPS product (Product-First flow)
   * POST /api/v1/contracts/products/
   */
  async createODPSProduct(data: ODPSProductCreateRequest): Promise<ODPSProductCreateResponse> {
    const response = await apiClient.getClient().post<ODPSProductCreateResponse>(
      `${CONTRACTS_BASE_PATH}/products/`,
      {
        original_raw: data.original_raw,
        original_format: data.original_format,
        resolve_external_refs: data.resolve_external_refs ?? true,
        asset_id: data.asset_id,
      },
      { timeout: 120000 }
    );
    return response.data;
  },

  /**
   * Get ODPS workflow status
   * GET /api/v1/contracts/products/workflows/{workflow_instance_id}/status/
   */
  async getWorkflowStatus(workflowInstanceId: string): Promise<ODPSWorkflowStatus> {
    const response = await apiClient.getClient().get<ODPSWorkflowStatus>(
      `${CONTRACTS_BASE_PATH}/products/workflows/${workflowInstanceId}/status/`
    );
    return response.data;
  },

  /**
   * Link ODPS to ODCS contract
   * POST /api/v1/contracts/{odcs_contract_id}/link-odps/
   */
  async linkODPS(odcsContractId: string, data: ODPSLinkRequest): Promise<ODPSLinkResponse> {
    const response = await apiClient.getClient().post<ODPSLinkResponse>(
      `${CONTRACTS_BASE_PATH}/${odcsContractId}/link-odps/`,
      {
        odps_contract_id: data.odps_contract_id,
        original_raw: data.original_raw,
        original_format: data.original_format,
        resolve_external_refs: data.resolve_external_refs ?? true,
      }
    );
    return response.data;
  },

  /**
   * Unlink ODPS from ODCS contract
   * POST /api/v1/contracts/{odcs_contract_id}/unlink-odps/
   */
  async unlinkODPS(odcsContractId: string): Promise<{ message: string }> {
    const response = await apiClient.getClient().post<{ message: string }>(
      `${CONTRACTS_BASE_PATH}/${odcsContractId}/unlink-odps/`
    );
    return response.data;
  },

  /**
   * Get contract links (ODPS ↔ ODCS)
   * GET /api/v1/contracts/{id}/links/
   */
  async getLinks(contractId: string): Promise<ODPSLinks> {
    const response = await apiClient.getClient().get<ODPSLinks>(
      `${CONTRACTS_BASE_PATH}/${contractId}/links/`
    );
    return response.data;
  },

  /**
   * Export ODPS contract with format options
   * GET /api/v1/contracts/{id}/export/?format=odps&output_format=json|yaml
   */
  async exportODPS(contractId: string, params: ODPSExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams();
    queryParams.append('format', params.format || 'odps');
    if (params.output_format) queryParams.append('output_format', params.output_format);
    if (params.version) queryParams.append('version', params.version);
    const response = await apiClient.getClient().get<Blob>(
      `${CONTRACTS_BASE_PATH}/${contractId}/export/?${queryParams.toString()}`,
      { responseType: 'blob' }
    );
    return response.data;
  },

  /**
   * Download ODPS contract with format options
   * GET /api/v1/contracts/{id}/download/?format=odps&output_format=json|yaml
   */
  async downloadODPS(contractId: string, params: ODPSExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams();
    queryParams.append('format', params.format || 'odps');
    if (params.output_format) queryParams.append('output_format', params.output_format);
    if (params.version) queryParams.append('version', params.version);
    const response = await apiClient.getClient().get<Blob>(
      `${CONTRACTS_BASE_PATH}/${contractId}/download/?${queryParams.toString()}`,
      { responseType: 'blob' }
    );
    return response.data;
  },

  // ---------------------------------------------------------------------------
  // Lineage
  // ---------------------------------------------------------------------------

  /**
   * Get contract lineage visualization (GET /api/v1/contracts/{id}/lineage/visualization/)
   * Returns nodes and links for graph visualization; no stub data.
   */
  async getLineageVisualization(
    id: string,
    params: ContractLineageVisualizationParams = {}
  ): Promise<ContractLineageVisualization> {
    const search = new URLSearchParams();
    search.set('format', params.format ?? 'json');
    if (params.max_depth != null) search.set('max_depth', String(params.max_depth));
    const url = `${CONTRACTS_BASE_PATH}/${id}/lineage/visualization/?${search.toString()}`;
    const response = await apiClient.getClient().get<ContractLineageVisualization>(url);
    return response.data;
  },
};
