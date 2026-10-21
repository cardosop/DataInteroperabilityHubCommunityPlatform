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

/**
 * ODPSTeamMember — a single entry in the Bitol `product.team.members` array.
 */
export interface ODPSTeamMember {
  name: string;
  email: string;
  role?: string;
  id?: string;
}

/**
 * ODPSPort — shared shape for output/input ports. Output ports typically carry
 * a `contractId` pointing to the ODCS contract governing the port.
 */
export interface ODPSPort {
  name: string;
  description?: string;
  contractId?: string;
  tags?: string[];
  type?: string;
}

/**
 * ODPSSchemaField — one field declared on an inline input schema.
 */
export interface ODPSSchemaField {
  name: string;
  type: string;
  description?: string;
  required?: boolean;
}

/**
 * ODPSInputSchema — declarative schema attached to an input port / dataset.
 */
export interface ODPSInputSchema {
  name: string;
  fields: ODPSSchemaField[];
}

/**
 * ODPSQualityRule — free-form quality expectation recorded on the product.
 */
export interface ODPSQualityRule {
  name: string;
  type?: string;
  expression?: string;
}

/**
 * ODPSSLAProperty — a single SLA entry (availability, latency, etc.).
 */
export interface ODPSSLAProperty {
  property: string;
  value: string;
  unit?: string;
}

/**
 * ODPSFormData — the editable shape used by the guided ODPS product form.
 *
 * The form covers the Bitol ODPS v1.0.0 fields most users need; anything not
 * represented here is preserved verbatim via `parseODPSDocument` /
 * `mergeODPSDocument` so round-tripping never drops user content.
 */
export interface ODPSFormData {
  // Envelope / root-level
  schema: string;
  apiVersion: string;
  kind: string;

  // Product details (language-keyed under product.details[language])
  language: string;
  productID: string;
  productName: string;
  productVersion: string;
  productStatus: string;
  productDescription: string;
  productDomain: string;
  productTenant: string;
  productVisibility: string;
  productCategory?: string;
  productType?: string;

  // Team and ports
  team: ODPSTeamMember[];
  outputPorts: ODPSPort[];
  inputPorts: ODPSPort[];
  inputSchemas: ODPSInputSchema[];

  // Quality and SLA
  slaProperties: ODPSSLAProperty[];
  qualityRules: ODPSQualityRule[];

  // Marketplace
  tags: string[];
  categories: string[];
  price?: number;
  currency?: string;
  licenseType?: string;
  marketplaceListed: boolean;
  marketplaceDescription?: string;

  // Linking
  linkedAssetId: string | null;
  linkedContractId: string | null;
}
