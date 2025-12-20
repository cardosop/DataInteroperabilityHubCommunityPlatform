/**
 * Contract API Service
 *
 * API functions for contract management operations:
 * - List contracts with filtering, sorting, and pagination
 * - Get single contract by ID
 * - Create new contract
 * - Update existing contract
 * - Validate contract
 * - Publish contract (if endpoint exists)
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Contract status enum
 */
export type ContractStatus = 'DRAFT' | 'ACTIVE' | 'RETIRED'

/**
 * Normalization status enum
 */
export type NormalizationStatus =
  | 'NORMALIZED_OK'
  | 'NORMALIZED_WITH_WARNINGS'
  | 'NORMALIZATION_FAILED'
  | 'NOT_NORMALIZED'

/**
 * Validation status enum
 */
export type ValidationStatus = 'VALID' | 'INVALID' | 'WARNING_ONLY' | 'ERROR'

/**
 * Contract hub_contract_json structure (simplified - full structure is complex)
 */
export interface HubContractJson {
  hub_contract_version: string
  id: string
  info?: {
    name?: string
    owners?: Array<{ name: string; email: string }>
    tags?: string[]
    [key: string]: any
  }
  schema?: {
    models?: Array<{
      name: string
      fields?: Array<{
        name: string
        type: string
        [key: string]: any
      }>
      [key: string]: any
    }>
    [key: string]: any
  }
  quality?: {
    rules?: Array<{
      name: string
      [key: string]: any
    }>
    [key: string]: any
  }
  privacy_compliance?: {
    [key: string]: any
  }
  lifecycle?: {
    [key: string]: any
  }
  marketplace?: {
    [key: string]: any
  }
  [key: string]: any
}

/**
 * Contract model
 */
export interface Contract {
  id: string
  hub_contract_json: HubContractJson
  status: ContractStatus
  normalization_status: NormalizationStatus
  validation_status?: ValidationStatus
  original_raw?: string | null
  original_format?: string | null
  original_spec_type?: string | null
  asset_id?: string | null
  created_at: string
  updated_at: string
  owners?: Array<{ name: string; email: string }>
  tags?: string[]
  quality_rules?: Array<{ name: string; [key: string]: any }>
  compliance_policy?: Record<string, any>
  lifecycle_policy?: Record<string, any>
  marketplace_policy?: Record<string, any>
  schema_fields?: Array<{
    name: string
    type: string
    [key: string]: any
  }>
}

/**
 * List contracts query parameters
 */
export interface ListContractsParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 50, max: 100)
   */
  page_size?: number
  /**
   * Sort fields (comma-separated, prefix with `-` for descending)
   * Example: "-created_at,quality_score"
   */
  ordering?: string
  /**
   * Filter by owner email (case-insensitive)
   */
  owner_email?: string
  /**
   * Filter by owner name (case-insensitive partial match)
   */
  owner_name?: string
  /**
   * Filter by tag (can specify multiple)
   */
  tag?: string | string[]
  /**
   * Filter by quality profile key
   */
  quality_profile?: string
  /**
   * Filter by compliance regime (e.g., GDPR, LGPD, CCPA)
   */
  compliance_regime?: string
  /**
   * Filter by contact email (case-insensitive)
   */
  contact_email?: string
  /**
   * Filter by contact name (case-insensitive partial match)
   */
  contact_name?: string
  /**
   * Filter by server type
   */
  server_type?: string
  /**
   * Filter by server URL (case-insensitive partial match)
   */
  server_url?: string
  /**
   * Filter by minimum availability SLA
   */
  min_availability?: number
  /**
   * Filter by maximum latency in milliseconds
   */
  max_latency_ms?: number
  /**
   * Filter by model name
   */
  model_name?: string
}

/**
 * Create contract request payload
 */
export interface CreateContractRequest {
  /**
   * Original contract content (JSON or YAML string)
   */
  original_raw: string
  /**
   * Original format (JSON or YAML)
   */
  original_format: 'JSON' | 'YAML'
  /**
   * Optional asset ID to associate with contract
   */
  asset_id?: string | null
  /**
   * Optional name (auto-generated if not provided)
   */
  name?: string | null
  /**
   * Optional description
   */
  description?: string | null
}

/**
 * Update contract request payload
 */
export interface UpdateContractRequest {
  /**
   * Original contract content (optional, triggers re-normalization if provided)
   */
  original_raw?: string | null
  /**
   * Original format (optional)
   */
  original_format?: 'JSON' | 'YAML' | null
  /**
   * Contract status (optional)
   */
  status?: ContractStatus
}

/**
 * Validate contract request payload
 */
export interface ValidateContractRequest {
  /**
   * Whether to run validation asynchronously
   * @default false
   */
  async?: boolean
}

/**
 * Validate contract response
 */
export interface ValidateContractResponse {
  /**
   * Validation status
   */
  validation_status: ValidationStatus
  /**
   * List of validation errors
   */
  errors: Array<{
    field?: string
    message: string
    [key: string]: any
  }>
  /**
   * List of validation warnings
   */
  warnings: Array<{
    field?: string
    message: string
    [key: string]: any
  }>
  /**
   * Grouped errors by category
   */
  grouped_errors?: Record<string, any>
  /**
   * DataContract CLI version used
   */
  cli_version?: string
  /**
   * Validation timestamp
   */
  validated_at?: string
  /**
   * Job ID (for async validation)
   */
  job_id?: string
  /**
   * Job status (for async validation)
   */
  status?: string
  /**
   * Job message (for async validation)
   */
  message?: string
}

/**
 * Publish contract request payload
 */
export interface PublishContractRequest {
  /**
   * Optional publish options
   */
  [key: string]: any
}

/**
 * Publish contract response
 */
export interface PublishContractResponse {
  /**
   * Contract ID
   */
  id: string
  /**
   * Updated contract status
   */
  status: ContractStatus
  /**
   * Publish timestamp
   */
  published_at?: string
  /**
   * Optional message
   */
  message?: string
}

/**
 * List contracts response
 */
export type ListContractsResponse = PaginatedResponse<Contract>

/**
 * List contracts with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of contracts
 */
export async function listContracts(
  params?: ListContractsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListContractsResponse> {
  // Handle tag array - convert to query params
  const queryParams: Record<string, any> = {
    page: params?.page,
    page_size: params?.page_size,
    ordering: params?.ordering,
    owner_email: params?.owner_email,
    owner_name: params?.owner_name,
    quality_profile: params?.quality_profile,
    compliance_regime: params?.compliance_regime,
    contact_email: params?.contact_email,
    contact_name: params?.contact_name,
    server_type: params?.server_type,
    server_url: params?.server_url,
    min_availability: params?.min_availability,
    max_latency_ms: params?.max_latency_ms,
    model_name: params?.model_name,
  }

  // Handle tag array - API expects multiple tag query params
  if (params?.tag) {
    const tags = Array.isArray(params.tag) ? params.tag : [params.tag]
    // Axios will handle array params correctly
    queryParams.tag = tags
  }

  const response = await apiClient.get<ListContractsResponse>('/api/v1/contracts/', {
    ...requestConfig,
    params: queryParams,
  })
  return response.data
}

/**
 * Get contract by ID
 *
 * @param id - Contract UUID
 * @param config - Optional Axios request config
 * @returns Contract details
 */
export async function getContract(id: string, config?: ExtendedFetchRequestInit): Promise<Contract> {
  const response = await apiClient.get<Contract>(`/api/v1/contracts/${id}/`, config)
  return response.data
}

/**
 * Create new contract
 *
 * @param data - Contract creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created contract
 */
export async function createContract(
  data: CreateContractRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Contract> {
  const response = await apiClient.post<Contract>('/api/v1/contracts/', data, requestConfig)
  return response.data
}

/**
 * Update existing contract
 *
 * @param id - Contract UUID
 * @param data - Contract update data
 * @param requestConfig - Optional Axios request config
 * @returns Updated contract
 */
export async function updateContract(
  id: string,
  data: UpdateContractRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Contract> {
  const response = await apiClient.patch<Contract>(`/api/v1/contracts/${id}/`, data, requestConfig)
  return response.data
}

/**
 * Validate contract
 *
 * @param id - Contract UUID
 * @param data - Validation options
 * @param requestConfig - Optional Axios request config
 * @returns Validation result
 */
export async function validateContract(
  id: string,
  data?: ValidateContractRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ValidateContractResponse> {
  const response = await apiClient.post<ValidateContractResponse>(
    `/api/v1/contracts/${id}/validate/`,
    data || {},
    requestConfig
  )
  return response.data
}

/**
 * Publish contract
 *
 * Note: This endpoint may not exist in all API versions.
 * If the endpoint doesn't exist, this will return an error.
 *
 * @param id - Contract UUID
 * @param data - Publish options
 * @param requestConfig - Optional Axios request config
 * @returns Published contract
 */
export async function publishContract(
  id: string,
  data?: PublishContractRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<PublishContractResponse> {
  const response = await apiClient.post<PublishContractResponse>(
    `/api/v1/contracts/${id}/publish/`,
    data || {},
    requestConfig
  )
  return response.data
}

/**
 * Delete contract (soft delete: sets status to RETIRED)
 *
 * @param id - Contract UUID
 * @param requestConfig - Optional Axios request config
 */
export async function deleteContract(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<void> {
  await apiClient.delete(`/api/v1/contracts/${id}/`, requestConfig)
}
