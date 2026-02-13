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
  normalization_status: NormalizationStatus;
  validation_status: ValidationStatus;
  created_at: string;
  updated_at: string;
  created_by: string;
  tenant_id: string;
  asset_id?: string;
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
