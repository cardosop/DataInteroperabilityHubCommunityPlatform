/**
 * Asset API Service
 *
 * API functions for asset management operations:
 * - List assets with filtering, sorting, and pagination
 * - Get single asset by ID
 * - Create new asset
 * - Update existing asset
 * - Delete asset
 */

import type { ExtendedFetchRequestInit } from './types'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Asset status enum
 */
export type AssetStatus = 'DRAFT' | 'ACTIVE' | 'PUBLIC' | 'RETIRED'

/**
 * Asset visibility enum
 */
export type AssetVisibility = 'INTERNAL' | 'PUBLIC'

/**
 * Data quality status enum
 */
export type DQStatus = 'UNKNOWN' | 'PASS' | 'WARN' | 'FAIL'

/**
 * Compliance status enum
 */
export type ComplianceStatus = 'UNKNOWN' | 'PASS' | 'WARN' | 'FAIL'

/**
 * Asset model
 */
export interface Asset {
  id: string
  tenant: string
  key: string
  name: string
  description: string | null
  domain: string | null
  status: AssetStatus
  visibility: AssetVisibility
  dq_status: DQStatus
  compliance_status: ComplianceStatus
  version: number
  created_by: string
  created_at: string
  updated_at: string
  contract_id?: string | null
  dataset_id?: string | null
  contract?: {
    id: string
    name: string
    status: string
  } | null
  dataset?: {
    id: string
    name: string
    format: string
  } | null
}

/**
 * List assets query parameters
 */
export interface ListAssetsParams {
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
   * Example: "name,-created_at"
   */
  ordering?: string
  /**
   * Search in name, key, description
   */
  search?: string
  /**
   * Filter by domain
   */
  domain?: string
  /**
   * Filter by tags (comma-separated)
   */
  tags?: string
  /**
   * Filter by status (DRAFT, ACTIVE, PUBLIC, RETIRED)
   */
  status?: AssetStatus
  /**
   * Filter by visibility (INTERNAL, PUBLIC)
   */
  visibility?: AssetVisibility
}

/**
 * Create asset request payload
 */
export interface CreateAssetRequest {
  /**
   * Human-friendly identifier, unique per tenant (required, max 255 chars)
   */
  key: string
  /**
   * Asset name (required, max 255 chars)
   */
  name: string
  /**
   * Asset description (optional, max 5000 chars)
   */
  description?: string | null
  /**
   * Domain (e.g., marketing, finance) (optional, max 100 chars)
   */
  domain?: string | null
  /**
   * Asset visibility (optional, default: INTERNAL)
   */
  visibility?: AssetVisibility
}

/**
 * Update asset request payload
 */
export interface UpdateAssetRequest {
  /**
   * Asset name (optional, max 255 chars)
   */
  name?: string
  /**
   * Asset description (optional, max 5000 chars)
   */
  description?: string | null
  /**
   * Domain (optional, max 100 chars)
   */
  domain?: string | null
  /**
   * Asset status (optional)
   */
  status?: AssetStatus
  /**
   * Asset visibility (optional)
   */
  visibility?: AssetVisibility
  /**
   * Current version for optimistic locking (required)
   */
  version: number
}

/**
 * List assets response
 */
export type ListAssetsResponse = PaginatedResponse<Asset>

/**
 * Get asset by ID
 *
 * @param id - Asset UUID
 * @param config - Optional Axios request config
 * @returns Asset details
 */
export async function getAsset(id: string, config?: ExtendedFetchRequestInit): Promise<Asset> {
  const response = await apiClient.get<Asset>(`/api/v1/assets/${id}/`, config)
  return response.data
}

/**
 * List assets with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of assets
 */
export async function listAssets(
  params?: ListAssetsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListAssetsResponse> {
  const response = await apiClient.get<ListAssetsResponse>('/api/v1/assets/', {
    ...requestConfig,
    params: {
      page: params?.page,
      page_size: params?.page_size,
      ordering: params?.ordering,
      search: params?.search,
      domain: params?.domain,
      tags: params?.tags,
      status: params?.status,
      visibility: params?.visibility,
    },
  })
  return response.data
}

/**
 * Create new asset
 *
 * @param data - Asset creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created asset
 */
export async function createAsset(
  data: CreateAssetRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Asset> {
  const response = await apiClient.post<Asset>('/api/v1/assets/', data, requestConfig)
  return response.data
}

/**
 * Update existing asset
 *
 * @param id - Asset UUID
 * @param data - Asset update data
 * @param requestConfig - Optional Axios request config
 * @returns Updated asset
 */
export async function updateAsset(
  id: string,
  data: UpdateAssetRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Asset> {
  const response = await apiClient.patch<Asset>(`/api/v1/assets/${id}/`, data, requestConfig)
  return response.data
}

/**
 * Delete asset
 *
 * @param id - Asset UUID
 * @param requestConfig - Optional Axios request config
 */
export async function deleteAsset(id: string, requestConfig?: ExtendedFetchRequestInit): Promise<void> {
  await apiClient.delete(`/api/v1/assets/${id}/`, requestConfig)
}
