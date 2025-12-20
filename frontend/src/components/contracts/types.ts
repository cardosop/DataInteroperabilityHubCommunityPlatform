/**
 * Contract Editor Type Definitions
 *
 * Comprehensive type definitions for HubContract and related structures
 * used in the Contract Editor component.
 */

/**
 * Owner information
 */
export interface Owner {
  name: string
  email: string
}

/**
 * Link information
 */
export interface Link {
  rel: string
  href: string
}

/**
 * Schema field data type
 */
export type SchemaFieldDataType =
  | 'string'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'date'
  | 'timestamp'
  | 'array'
  | 'object'

/**
 * Schema field semantic type
 */
export type SchemaFieldSemanticType =
  | 'EMAIL'
  | 'PHONE'
  | 'ORDER_ID'
  | 'CUSTOMER_ID'
  | 'PRODUCT_ID'
  | 'ADDRESS'
  | 'NAME'
  | 'DATE'
  | 'CURRENCY'
  | 'PERCENTAGE'
  | string

/**
 * Schema field definition
 */
export interface SchemaField {
  name: string
  data_type: SchemaFieldDataType
  nullable?: boolean
  description?: string
  semantic_type?: SchemaFieldSemanticType
  format?: string
  pattern?: string
  enum?: any[]
  default?: any
  min_length?: number
  max_length?: number
  minimum?: number
  maximum?: number
  metadata?: Record<string, any>
  is_primary_key?: boolean
  is_unique?: boolean
  is_indexed?: boolean
}

/**
 * Quality rule dimension
 */
export type QualityRuleDimension =
  | 'completeness'
  | 'validity'
  | 'uniqueness'
  | 'consistency'
  | 'accuracy'
  | 'timeliness'

/**
 * Quality rule severity
 */
export type QualityRuleSeverity = 'ERROR' | 'WARNING' | 'INFO'

/**
 * Quality rule target level
 */
export type QualityRuleTargetLevel = 'COLUMN' | 'TABLE' | 'DATASET'

/**
 * Quality rule definition
 */
export interface QualityRule {
  rule_id: string
  name: string
  dimension: QualityRuleDimension
  expression?: string
  severity: QualityRuleSeverity
  target_level?: QualityRuleTargetLevel
  target_column?: string
  target_pattern?: string
  params?: Record<string, any>
}

/**
 * Compliance jurisdiction
 */
export type ComplianceJurisdiction = 'GDPR' | 'LGPD' | 'CCPA' | 'HIPAA' | 'SOX'

/**
 * Legal basis
 */
export type LegalBasis =
  | 'CONSENT'
  | 'CONTRACT'
  | 'LEGAL_OBLIGATION'
  | 'VITAL_INTERESTS'
  | 'PUBLIC_TASK'
  | 'LEGITIMATE_INTERESTS'

/**
 * Personal data category
 */
export type PersonalDataCategory =
  | 'EMAIL'
  | 'PHONE'
  | 'NAME'
  | 'ADDRESS'
  | 'SSN'
  | 'IP_ADDRESS'
  | 'LOCATION'
  | 'FINANCIAL'
  | string

/**
 * Retention policy
 */
export interface RetentionPolicy {
  period?: string // ISO 8601 duration (e.g., "P5Y", "P1Y")
  notes?: string
}

/**
 * Refresh cadence
 */
export type RefreshCadence =
  | 'REAL_TIME'
  | 'HOURLY'
  | 'DAILY'
  | 'WEEKLY'
  | 'MONTHLY'
  | 'ON_DEMAND'

/**
 * Service level agreements
 */
export interface SLAs {
  availability?: number // Percentage (e.g., 99.0)
  latency_ms_p95?: number // Milliseconds (e.g., 5000)
}

/**
 * Intended use case
 */
export type IntendedUse =
  | 'analytics'
  | 'machine_learning'
  | 'reporting'
  | 'data_integration'
  | 'compliance'
  | string

/**
 * Restricted use case
 */
export type RestrictedUse =
  | 'resale'
  | 'competitive_analysis'
  | 'marketing'
  | 'third_party_sharing'
  | string

/**
 * Complete HubContract structure
 */
export interface HubContract {
  hub_contract_version: number
  id: string
  info: {
    name: string
    description?: string
    version?: string
    owners?: Owner[]
    tags?: string[]
    domain?: string
    status?: string
    dataProduct?: string
    links?: Link[]
    authoritativeDefinitions?: string[]
  }
  schema: {
    fields: SchemaField[]
    primary_key?: string[]
    unique_constraints?: string[][]
    indexes?: string[][]
  }
  quality?: {
    default_profile_key?: string
    rules?: QualityRule[]
  }
  privacy_compliance?: {
    contains_personal_data?: boolean
    personal_data_categories?: PersonalDataCategory[]
    jurisdictions?: ComplianceJurisdiction[]
    legal_bases?: LegalBasis[]
    retention_policy?: RetentionPolicy
  }
  lifecycle?: {
    data_source?: string
    refresh_cadence?: RefreshCadence
    slas?: SLAs
  }
  marketplace?: {
    license_summary?: string
    intended_use?: IntendedUse[]
    restricted_use?: RestrictedUse[]
  }
  extensions?: {
    odcs?: Record<string, any>
    datacontract_com?: Record<string, any>
    [key: string]: any
  }
}

/**
 * Validation error
 */
export interface ValidationError {
  field?: string
  message: string
  code?: string
  [key: string]: any
}

/**
 * Validation warning
 */
export interface ValidationWarning {
  field?: string
  message: string
  severity?: 'low' | 'medium' | 'high'
  [key: string]: any
}

/**
 * Validation result
 */
export interface ValidationResult {
  validation_status: 'VALID' | 'INVALID' | 'WARNING_ONLY' | 'ERROR'
  errors: ValidationError[]
  warnings: ValidationWarning[]
  grouped_errors?: Record<string, ValidationError[]>
  cli_version?: string
  validated_at?: string
}

/**
 * Normalization status
 */
export type NormalizationStatus =
  | 'NORMALIZED_OK'
  | 'NORMALIZED_WITH_WARNINGS'
  | 'NORMALIZATION_FAILED'
  | 'NOT_NORMALIZED'

/**
 * Validation status
 */
export type ValidationStatus = 'VALID' | 'INVALID' | 'WARNING_ONLY' | 'ERROR'

/**
 * Schema comparison result
 */
export interface SchemaComparison {
  inferredSchema: SchemaField[]
  contractSchema: SchemaField[]
  differences: {
    added: SchemaField[]
    removed: SchemaField[]
    modified: Array<{
      field: string
      inferred: SchemaField
      contract: SchemaField
      differences: string[]
    }>
  }
}

/**
 * Editor mode
 */
export type EditorMode = 'form' | 'yaml' | 'visual'

/**
 * Onboarding flow type
 */
export type OnboardingFlow = 'data-first' | 'contract-first' | 'contract-only'

/**
 * Contract editor props
 */
export interface ContractEditorProps {
  contractId?: string
  assetId?: string
  initialContract?: HubContract
  mode?: 'create' | 'edit'
  onboardingFlow?: OnboardingFlow
  inferredSchema?: SchemaField[]
  onSave: (contract: HubContract) => Promise<void>
  onValidate: (contract: HubContract) => Promise<ValidationResult>
  onCancel: () => void
}

/**
 * Contract editor state
 */
export interface ContractEditorState {
  contract: HubContract
  activeTab: string
  validationStatus?: ValidationStatus
  normalizationStatus?: NormalizationStatus
  isDirty: boolean
  isSaving: boolean
  isValidating: boolean
  errors: ValidationError[]
  warnings: ValidationWarning[]
  schemaComparison?: SchemaComparison
}

