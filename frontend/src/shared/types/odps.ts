/**
 * ODPS (Open Data Product Standard) Types
 * Based on backend ODPS API endpoints
 */

import type { Contract, ContractFormat } from './contracts';

export interface ODPSProductCreateRequest {
  original_raw: string;
  original_format: ContractFormat;
  resolve_external_refs?: boolean;
  asset_id?: string;
}

export interface ODPSProductCreateResponse {
  workflow_instance_id: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED';
  message?: string;
}

export interface ODPSWorkflowStatus {
  workflow_instance_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  odps_contract?: Contract;
  odcs_contract?: Contract;
  message?: string;
  progress_percentage?: number;
  current_step_name?: string;
}

export interface ODPSLinkRequest {
  odps_contract_id?: string;
  original_raw?: string;
  original_format?: ContractFormat;
  resolve_external_refs?: boolean;
}

export interface ODPSLinkResponse {
  id: string;
  original_spec_type: string;
  original_spec_version: string;
  status: string;
  normalization_status: string;
  hub_contract_json: Record<string, unknown>;
  created_at: string;
}

export interface ODPSLinks {
  odps_link: Contract | null;
  odcs_link: Contract | null;
}

export interface ODPSExportParams {
  format?: 'odps' | 'odcs' | 'hubcontract';
  output_format?: 'json' | 'yaml';
  version?: string;
}
