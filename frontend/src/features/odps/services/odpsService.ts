/**
 * ODPS Service
 * API client for ODPS operations
 */

import { apiClient } from '../../../shared/api/client';
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

export const odpsService = {
  /**
   * Create ODPS product (Product-First flow)
   * POST /api/v1/contracts/products/
   */
  async createProduct(data: ODPSProductCreateRequest): Promise<ODPSProductCreateResponse> {
    const response = await apiClient.getClient().post<ODPSProductCreateResponse>(
      `${CONTRACTS_BASE_PATH}/products/`,
      {
        original_raw: data.original_raw,
        original_format: data.original_format,
        resolve_external_refs: data.resolve_external_refs ?? true,
        asset_id: data.asset_id,
      }
    );
    return response.data;
  },

  /**
   * Get ODPS product creation workflow status
   * GET /api/v1/contracts/products/{workflow_instance_id}/status/
   */
  async getWorkflowStatus(workflowInstanceId: string): Promise<ODPSWorkflowStatus> {
    const response = await apiClient.getClient().get<ODPSWorkflowStatus>(
      `${CONTRACTS_BASE_PATH}/products/${workflowInstanceId}/status/`
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
   * Export ODPS contract
   * GET /api/v1/contracts/{id}/export/?format=odps&output_format=json|yaml
   */
  async exportODPS(contractId: string, params: ODPSExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams();
    queryParams.append('format', params.format || 'odps');
    if (params.output_format) {
      queryParams.append('output_format', params.output_format);
    }
    if (params.version) {
      queryParams.append('version', params.version);
    }

    const response = await apiClient.getClient().get(
      `${CONTRACTS_BASE_PATH}/${contractId}/export/?${queryParams.toString()}`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  /**
   * Download ODPS contract
   * GET /api/v1/contracts/{id}/download/?format=odps&output_format=json|yaml
   */
  async downloadODPS(contractId: string, params: ODPSExportParams = {}): Promise<Blob> {
    const queryParams = new URLSearchParams();
    queryParams.append('format', params.format || 'odps');
    if (params.output_format) {
      queryParams.append('output_format', params.output_format);
    }
    if (params.version) {
      queryParams.append('version', params.version);
    }

    const response = await apiClient.getClient().get(
      `${CONTRACTS_BASE_PATH}/${contractId}/download/?${queryParams.toString()}`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },
};
