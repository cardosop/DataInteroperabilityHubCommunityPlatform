/**
 * Marketplace API Service
 *
 * API functions for marketplace operations:
 * - Search contracts in marketplace
 * - Get single listing
 * - Get listing preview (asset, dataset, quality metrics)
 * - Download contracts from marketplace listings
 * - Create orders (access requests)
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Listing status enum
 */
export type ListingStatus = 'DRAFT' | 'PUBLISHED' | 'UNLISTED' | 'DELETED'

/**
 * Pricing model enum
 */
export type PricingModel = 'FREE' | 'FREE_AUTO_APPROVE' | 'REQUEST_APPROVAL'

/**
 * Marketplace listing model
 */
export interface MarketplaceListing {
  id: string
  tenant: string
  asset: string
  status: ListingStatus
  pricing_model: PricingModel
  metadata_json: {
    title?: string
    short_description?: string
    long_description?: string
    price_amount?: number
    currency?: string
    tags?: string[]
    domain?: string
    [key: string]: any
  }
  published_at: string | null
  created_at: string
  updated_at: string
  // Convenience fields extracted from metadata_json
  title?: string | null
  description?: string | null
  short_description?: string | null
  long_description?: string | null
  price_amount?: number | null
  currency?: string | null
  tags?: string[]
  domain?: string | null
}

/**
 * Search marketplace contracts query parameters
 */
export interface SearchMarketplaceContractsParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 20)
   */
  page_size?: number
  /**
   * Search query (searches in title and descriptions)
   */
  search?: string
  /**
   * Filter by domain
   */
  domain?: string
  /**
   * Filter by tags (array)
   */
  tags?: string[]
  /**
   * Filter by owner (tenant_id)
   */
  owner?: string
  /**
   * Filter by minimum price
   */
  price_min?: number
  /**
   * Filter by maximum price
   */
  price_max?: number
  /**
   * Filter by access mode (pricing_model)
   */
  access_mode?: PricingModel
}

/**
 * Search marketplace contracts response
 */
export interface SearchMarketplaceContractsResponse {
  results: MarketplaceListing[]
  count: number
  page: number
  page_size: number
}

/**
 * Download contract request parameters
 */
export interface DownloadContractParams {
  /**
   * Listing ID
   */
  listingId: string
  /**
   * Format: 'original' (original_raw) or 'json' (hub_contract_json)
   * Default: 'original'
   */
  format?: 'original' | 'json'
}

/**
 * Download contract response
 */
export interface DownloadContractResponse {
  /**
   * Contract ID
   */
  contract_id: string
  /**
   * Contract content (JSON string or original format)
   */
  contract_content: string
  /**
   * Format: JSON, YAML, etc.
   */
  format: string
  /**
   * Suggested filename
   */
  filename: string
}

/**
 * Search contracts in marketplace
 *
 * Searches for published marketplace listings (contracts).
 * Only returns listings from verified tenants.
 *
 * @param params - Query parameters for search and filtering
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of marketplace listings
 *
 * @example
 * ```ts
 * const results = await searchMarketplaceContracts({
 *   search: 'customer data',
 *   domain: 'marketing',
 *   tags: ['analytics', 'customer'],
 *   page: 1,
 *   page_size: 20
 * })
 * ```
 */
export async function searchMarketplaceContracts(
  params?: SearchMarketplaceContractsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<SearchMarketplaceContractsResponse> {
  const queryParams: Record<string, any> = {
    page: params?.page,
    page_size: params?.page_size,
    search: params?.search,
    domain: params?.domain,
    owner: params?.owner,
    price_min: params?.price_min,
    price_max: params?.price_max,
    access_mode: params?.access_mode,
  }

  // Handle tags array
  if (params?.tags && params.tags.length > 0) {
    queryParams.tags = params.tags
  }

  const response = await apiClient.get<SearchMarketplaceContractsResponse>(
    '/api/v1/marketplace/listings/search/',
    {
      ...requestConfig,
      params: queryParams,
    }
  )
  return response.data
}

/**
 * Download contract from marketplace listing
 *
 * Downloads the contract file for a marketplace listing.
 * Requires active entitlement for cross-tenant access.
 *
 * @param params - Download parameters
 * @param requestConfig - Optional Axios request config
 * @returns Contract download response with content and metadata
 *
 * @example
 * ```ts
 * const download = await downloadMarketplaceContract({
 *   listingId: 'listing-123',
 *   format: 'original' // or 'json'
 * })
 *
 * // Save to file
 * const blob = new Blob([download.contract_content], {
 *   type: download.format === 'JSON' ? 'application/json' : 'text/plain'
 * })
 * const url = URL.createObjectURL(blob)
 * const a = document.createElement('a')
 * a.href = url
 * a.download = download.filename
 * a.click()
 * ```
 */
export async function downloadMarketplaceContract(
  params: DownloadContractParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<DownloadContractResponse> {
  const queryParams: Record<string, any> = {}
  if (params.format) {
    queryParams.format = params.format
  }

  const response = await apiClient.get<DownloadContractResponse>(
    `/api/v1/marketplace/listings/${params.listingId}/download/`,
    {
      ...requestConfig,
      params: queryParams,
    }
  )
  return response.data
}

/**
 * Listing preview response (includes asset, dataset, quality metrics, schema)
 */
export interface ListingPreviewResponse {
  listing_id: string
  asset_id: string
  sample_data: {
    rows: any[]
    total_rows: number
    sample_size: number
  }
  quality_metrics: {
    completeness: number
    accuracy: number
    freshness: string
    overall_score: number
  } | null
  schema: {
    fields: Array<{
      name: string
      type: string
      nullable: boolean
    }>
  } | null
  preview_expires_at: string
}

/**
 * Create order request
 */
export interface CreateOrderRequest {
  /**
   * Listing ID to create order for
   */
  listing_id: string
}

/**
 * Order model
 */
export interface Order {
  id: string
  tenant: string
  listing: string
  status: 'REQUESTED' | 'APPROVED' | 'REJECTED' | 'CANCELLED' | 'FULFILLED'
  created_by: string | null
  approved_by: string | null
  metadata_json: Record<string, any> | null
  approved_at: string | null
  rejected_at: string | null
  fulfilled_at: string | null
  created_at: string
  updated_at: string
  // Convenience fields
  listing_title?: string | null
  asset_id?: string | null
  rejection_reason?: string | null
}

/**
 * Create order response
 */
export interface CreateOrderResponse {
  order: Order
  entitlement?: {
    id: string
    tenant_id: string
    asset_id: string
    listing_id: string
    order_id: string | null
    status: string
    granted_at: string | null
  } | null
}

/**
 * Get marketplace listing by ID
 *
 * @param id - Listing UUID
 * @param requestConfig - Optional Axios request config
 * @returns Marketplace listing details
 *
 * @example
 * ```ts
 * const listing = await getMarketplaceListing('listing-123')
 * ```
 */
export async function getMarketplaceListing(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<MarketplaceListing> {
  const response = await apiClient.get<MarketplaceListing>(
    `/api/v1/marketplace/listings/${id}/`,
    requestConfig
  )
  return response.data
}

/**
 * Get marketplace listing preview
 *
 * Returns asset, dataset, quality metrics, and schema preview for a listing.
 *
 * @param id - Listing UUID
 * @param requestConfig - Optional Axios request config
 * @returns Listing preview with asset, dataset, quality metrics, and schema
 *
 * @example
 * ```ts
 * const preview = await getMarketplaceListingPreview('listing-123')
 * console.log(preview.quality_metrics)
 * console.log(preview.schema)
 * ```
 */
export async function getMarketplaceListingPreview(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListingPreviewResponse> {
  const response = await apiClient.get<ListingPreviewResponse>(
    `/api/v1/marketplace/listings/${id}/preview/`,
    requestConfig
  )
  return response.data
}

/**
 * Create marketplace order (access request)
 *
 * Creates an order to request access to a marketplace listing.
 * For FREE_AUTO_APPROVE listings, the order is automatically approved and fulfilled.
 * For REQUEST_APPROVAL listings, the order requires manual approval.
 *
 * @param data - Order creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created order (and entitlement if auto-approved)
 *
 * @example
 * ```ts
 * const result = await createMarketplaceOrder({
 *   listing_id: 'listing-123'
 * })
 * console.log(result.order.status) // 'FULFILLED' for auto-approved, 'REQUESTED' for manual
 * ```
 */
export async function createMarketplaceOrder(
  data: CreateOrderRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<CreateOrderResponse> {
  const response = await apiClient.post<CreateOrderResponse>(
    '/api/v1/marketplace/orders/',
    data,
    requestConfig
  )
  return response.data
}

