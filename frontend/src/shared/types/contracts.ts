/**
 * Contract Types
 * Based on backend ContractSerializer and Contract model
 */

export const ContractFormat = {
  JSON: 'JSON',
  YAML: 'YAML',
} as const;
export type ContractFormat = (typeof ContractFormat)[keyof typeof ContractFormat];

export const NormalizationStatus = {
  NORMALIZED_OK: 'NORMALIZED_OK',
  NORMALIZED_WITH_WARNINGS: 'NORMALIZED_WITH_WARNINGS',
  NORMALIZATION_FAILED: 'NORMALIZATION_FAILED',
  NOT_NORMALIZED: 'NOT_NORMALIZED',
} as const;
export type NormalizationStatus = (typeof NormalizationStatus)[keyof typeof NormalizationStatus];

export const ValidationStatus = {
  VALID: 'VALID',
  INVALID: 'INVALID',
  WARNING_ONLY: 'WARNING_ONLY',
  ERROR: 'ERROR',
} as const;
export type ValidationStatus = (typeof ValidationStatus)[keyof typeof ValidationStatus];

export interface Contract {
  id: string;
  name?: string;
  description?: string;
  original_raw: string;
  original_format: ContractFormat;
  original_spec_type?: string;
  hub_contract_json: Record<string, unknown>;
  /** Contract lifecycle: DRAFT → ACTIVE → RETIRED. */
  status?: 'DRAFT' | 'ACTIVE' | 'RETIRED';
  normalization_status: NormalizationStatus;
  validation_status: ValidationStatus;
  created_at: string;
  updated_at: string;
  created_by: string;
  tenant_id: string;
  /** Linked asset UUID; API may expose this and/or `asset` (same value). */
  asset_id?: string | null;
  asset?: string | null;
  // Computed fields from hub_contract_json
  owners?: Array<{ name: string; email: string }>;
  tags?: string[];
  quality_rules?: Array<Record<string, unknown>>;
  compliance_policy?: Record<string, unknown>;
  lifecycle_policy?: Record<string, unknown>;
  marketplace_policy?: Record<string, unknown>;
  schema_fields?: Array<Record<string, unknown>>;
}

export interface ContractCreateRequest {
  original_raw: string;
  original_format: ContractFormat;
  original_spec_type?: string;
  asset_id?: string;
  name?: string;
  description?: string;
}

export interface ContractUpdateRequest {
  original_raw?: string;
  original_format?: ContractFormat;
  name?: string;
  description?: string;
}

export interface ContractListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  owner_email?: string;
  owner_name?: string;
  tag?: string;
  quality_profile?: string;
  compliance_regime?: string;
  asset_id?: string;
  /** Filter by original_spec_type (e.g. ODPS, ODCS) for ODPS Link page */
  spec_type?: string;
}

export interface ContractValidationResult {
  valid: boolean;
  errors?: Array<{
    field?: string;
    message: string;
    code: string;
  }>;
  warnings?: Array<{
    field?: string;
    message: string;
    code: string;
  }>;
}

/** Dry-run normalization result from POST /contracts/validate-draft/ (Phase 219.4). */
export interface DraftValidationResult {
  valid: boolean;
  detected_spec_type: string;
  detected_spec_version: string;
  normalization_status: string;
  normalization_errors: string[];
  normalization_warnings: string[];
}

export interface ContractLintResult {
  valid: boolean;
  issues?: Array<{
    severity: 'error' | 'warning' | 'info';
    message: string;
    field?: string;
    code: string;
  }>;
}

export interface ContractConvertRequest {
  target_format: ContractFormat;
}

export interface ContractConvertResult {
  converted_raw: string;
  format: ContractFormat;
}

/** Supported ODCS export versions */
export const ODCS_EXPORT_VERSIONS = [
  '2.2.2',
  '3.0.0',
  '3.0.1',
  '3.0.2',
  '3.1.0',
] as const;

export type ODCSExportVersion = (typeof ODCS_EXPORT_VERSIONS)[number];

/** A relationship entry from hub_contract_json models */
/** Resolved linked asset id from contract payload (DRF uses `asset`; clients often use `asset_id`). */
export function getContractLinkedAssetId(contract: Contract): string | null {
  const id = contract.asset_id ?? contract.asset;
  if (id == null || id === '') {
    return null;
  }
  return String(id);
}

export interface ContractRelationship {
  id?: string;
  type?: string;
  source?: string[];
  target_contract?: string;
  target_model?: string;
  target_properties?: string[];
  description?: string;
}

/** A schema object (model) from hub_contract_json */
export interface ContractSchemaObject {
  name: string;
  description?: string;
  relationships?: ContractRelationship[];
  [key: string]: unknown;
}
