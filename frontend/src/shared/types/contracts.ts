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

/* -------------------------------------------------------------------------
 * Phase 227 Wave 1 (227.L5.10) — Schema editor state types
 *
 * The editor is hub-shaped (models[*].fields[*]) regardless of the
 * source spec; the compiler at ``contractsCompiler.ts`` projects the
 * editor state to ODCS or ODPS source on save and parses incoming raw
 * back into editor state on load.
 * ------------------------------------------------------------------------- */

/** Canonical data-types accepted by the editor; matches HubContractField. */
export const FIELD_DATA_TYPES = [
  'string',
  'integer',
  'number',
  'boolean',
  'date',
  'date-time',
  'time',
  'object',
  'array',
] as const;
export type EditorFieldDataType = (typeof FIELD_DATA_TYPES)[number];

/**
 * One field row in the editor — the recursive shape mirrors
 * HubContractField (Phase 227 L2.2). ``fields`` is populated when
 * ``data_type === 'object'``; ``items`` when ``'array'``.
 *
 * The editor stores extra UI-only state under leading-underscore keys
 * (``_uiKey``) so they can be stripped before compilation.
 */
export interface EditorField {
  /** Stable client-side identity for React keys. */
  _uiKey: string;
  name: string;
  data_type: EditorFieldDataType;
  description?: string;
  nullable?: boolean;
  format?: string;
  pattern?: string;
  enum?: Array<string | number>;
  default?: unknown;
  min_length?: number;
  max_length?: number;
  minimum?: number;
  maximum?: number;
  is_primary_key?: boolean;
  is_unique?: boolean;
  is_indexed?: boolean;
  /** Object-typed fields carry nested children. */
  fields?: EditorField[];
  /** Array-typed fields carry one item schema. */
  items?: EditorField;
}

/** One model in the editor. */
export interface EditorModel {
  _uiKey: string;
  name: string;
  description?: string;
  fields: EditorField[];
  primary_key?: string[];
  tags?: string[];
}

/** Top-level editor state — what ``ModelsEditor`` reads/writes. */
export interface SchemaEditorState {
  /** Source spec the contract was loaded from. */
  specType: 'ODCS' | 'ODPS';
  /** Source spec version (e.g. "3.1.0", "bitol-1.0.0"). */
  specVersion: string;
  /** Top-level info preserved across edit/save round-trip. */
  info: {
    name?: string;
    description?: string;
    version?: string;
    status?: string;
  };
  models: EditorModel[];
  /** ETag from the GET that loaded this state — sent as If-Match on save. */
  etag?: string | null;
  /** Original raw content; carried so we can preserve unrecognised fields. */
  originalRaw?: string;
}

/** Result envelope from ``GET /contracts/schema/json-schema/``. */
export interface ContractJsonSchemaResponse {
  spec: 'odcs' | 'odps' | null;
  schema: Record<string, unknown>;
}

/** Per-model client-side validation issue surfaced in the editor UI. */
export interface EditorValidationIssue {
  modelIndex: number;
  fieldPath?: string;
  message: string;
  code:
    | 'MODEL_NAME_REQUIRED'
    | 'MODEL_FIELDS_REQUIRED'
    | 'FIELD_NAME_REQUIRED'
    | 'FIELD_NAME_DUPLICATE'
    | 'OBJECT_FIELD_REQUIRES_NESTED_FIELDS'
    | 'ARRAY_FIELD_REQUIRES_ITEMS';
}
