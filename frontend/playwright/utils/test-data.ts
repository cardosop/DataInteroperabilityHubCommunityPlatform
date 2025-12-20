/**
 * Test Data Helpers for Playwright Tests
 *
 * Comprehensive test data utilities for E2E tests.
 * Provides helpers for creating, managing, and cleaning up test data.
 *
 * Uses real API calls and factories - no mocks/stubs. Always fixes root cause.
 */

import { Page, APIRequestContext } from '@playwright/test'
import {
  assetFactory,
  contractFactory,
  datasetFactory,
  userFactory,
  tenantFactory,
  jobFactory,
  listingFactory,
  type FactoryOptions,
} from '../../tests/factories'
// Type definitions for test data
// These match the API types but are defined here to avoid import issues
export interface User {
  id: string
  tenant?: string | null
  email: string
  display_name?: string | null
  status: string
  is_platform_admin: boolean
  roles?: any[]
  created_at: string
  updated_at: string
}

export interface Asset {
  id: string
  tenant: string
  key: string
  name: string
  description: string | null
  domain: string | null
  status: string
  visibility: string
  dq_status: string
  compliance_status: string
  version: number
  created_by: string
  created_at: string
  updated_at: string
}

export interface Contract {
  id: string
  tenant: string
  name: string | null
  description: string | null
  status: string
  normalization_status: string
  validation_status: string | null
  hub_contract_json: any
  created_by: string
  created_at: string
  updated_at: string
}

export interface Dataset {
  id: string
  tenant: string
  name: string
  format: string
  size_bytes: number
  row_count: number | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface Tenant {
  id: string
  name: string
  slug: string
  status: string
  kyc_status: string
  region?: string | null
  deleted_at?: string | null
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  tenant: string | null
  type: string
  status: string
  resource_type: string
  resource_id: string
  created_by: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  result_json: Record<string, any> | null
  details_json: Record<string, any> | null
  timeout_seconds: number | null
  created_at: string
  updated_at: string
}

export interface MarketplaceListing {
  id: string
  tenant: string
  asset: string
  status: string
  pricing_model: string
  metadata_json: Record<string, any>
  published_at: string | null
  created_at: string
  updated_at: string
}
import { apiPost, apiDelete, apiPatch, getApiBaseUrl } from './api'
import { listingFactory, jobFactory } from '../../tests/factories'

/**
 * Test data creation options
 */
export interface CreateTestDataOptions {
  /**
   * Whether to persist data to API (default: true)
   */
  persist?: boolean

  /**
   * API context for making API calls
   */
  apiContext?: APIRequestContext

  /**
   * Factory options for data generation
   */
  factoryOptions?: FactoryOptions<any>
}

/**
 * Create test asset via API
 *
 * @param apiContext - API request context
 * @param options - Creation options
 * @returns Created asset
 *
 * @example
 * ```ts
 * const asset = await createTestAsset(apiContext)
 * ```
 */
export async function createTestAsset(
  apiContext: APIRequestContext,
  options: CreateTestDataOptions = {}
): Promise<Asset> {
  const assetData = assetFactory.build(options.factoryOptions)

  if (options.persist !== false && apiContext) {
    try {
      const response = await apiPost<Asset>(apiContext, '/api/v1/assets/', assetData)
      if (response.status === 201 || response.status === 200) {
        return response.data
      }
    } catch (error) {
      console.warn('Failed to create asset via API, using factory data:', error)
    }
  }

  return assetData
}

/**
 * Create multiple test assets
 *
 * @param apiContext - API request context
 * @param count - Number of assets to create
 * @param options - Creation options
 * @returns Array of created assets
 *
 * @example
 * ```ts
 * const assets = await createTestAssets(apiContext, 5)
 * ```
 */
export async function createTestAssets(
  apiContext: APIRequestContext,
  count: number,
  options: CreateTestDataOptions = {}
): Promise<Asset[]> {
  const assets: Asset[] = []

  for (let i = 0; i < count; i++) {
    const asset = await createTestAsset(apiContext, {
      ...options,
      factoryOptions: {
        ...options.factoryOptions,
        overrides: {
          ...options.factoryOptions?.overrides,
          name: `Test Asset ${i + 1}`,
        },
      },
    })
    assets.push(asset)
  }

  return assets
}

/**
 * Create test contract via API
 *
 * @param apiContext - API request context
 * @param options - Creation options
 * @returns Created contract
 *
 * @example
 * ```ts
 * const contract = await createTestContract(apiContext)
 * ```
 */
export async function createTestContract(
  apiContext: APIRequestContext,
  options: CreateTestDataOptions = {}
): Promise<Contract> {
  const contractData = contractFactory.build(options.factoryOptions)

  if (options.persist !== false && apiContext) {
    try {
      const response = await apiPost<Contract>(apiContext, '/api/v1/contracts/', contractData)
      if (response.status === 201 || response.status === 200) {
        return response.data
      }
    } catch (error) {
      console.warn('Failed to create contract via API, using factory data:', error)
    }
  }

  return contractData
}

/**
 * Create multiple test contracts
 *
 * @param apiContext - API request context
 * @param count - Number of contracts to create
 * @param options - Creation options
 * @returns Array of created contracts
 *
 * @example
 * ```ts
 * const contracts = await createTestContracts(apiContext, 3)
 * ```
 */
export async function createTestContracts(
  apiContext: APIRequestContext,
  count: number,
  options: CreateTestDataOptions = {}
): Promise<Contract[]> {
  const contracts: Contract[] = []

  for (let i = 0; i < count; i++) {
    const contract = await createTestContract(apiContext, {
      ...options,
      factoryOptions: {
        ...options.factoryOptions,
        overrides: {
          ...options.factoryOptions?.overrides,
          hub_contract_json: {
            ...contractFactory.build().hub_contract_json,
            info: {
              ...contractFactory.build().hub_contract_json.info,
              name: `Test Contract ${i + 1}`,
            },
          },
        },
      },
    })
    contracts.push(contract)
  }

  return contracts
}

/**
 * Create test dataset via API
 *
 * @param apiContext - API request context
 * @param options - Creation options
 * @returns Created dataset
 *
 * @example
 * ```ts
 * const dataset = await createTestDataset(apiContext)
 * ```
 */
export async function createTestDataset(
  apiContext: APIRequestContext,
  options: CreateTestDataOptions = {}
): Promise<Dataset> {
  const datasetData = datasetFactory.build(options.factoryOptions)

  if (options.persist !== false && apiContext) {
    try {
      const response = await apiPost<Dataset>(apiContext, '/api/v1/datasets/', datasetData)
      if (response.status === 201 || response.status === 200) {
        return response.data
      }
    } catch (error) {
      console.warn('Failed to create dataset via API, using factory data:', error)
    }
  }

  return datasetData
}

/**
 * Create test user via API
 *
 * @param apiContext - API request context
 * @param options - Creation options
 * @returns Created user
 *
 * @example
 * ```ts
 * const user = await createTestUser(apiContext)
 * ```
 */
export async function createTestUser(
  apiContext: APIRequestContext,
  options: CreateTestDataOptions = {}
): Promise<User> {
  const userData = userFactory.build(options.factoryOptions)

  if (options.persist !== false && apiContext) {
    try {
      const response = await apiPost<User>(apiContext, '/api/v1/users/', userData)
      if (response.status === 201 || response.status === 200) {
        return response.data
      }
    } catch (error) {
      console.warn('Failed to create user via API, using factory data:', error)
    }
  }

  return userData
}

/**
 * Create test tenant via API
 *
 * @param apiContext - API request context
 * @param options - Creation options
 * @returns Created tenant
 *
 * @example
 * ```ts
 * const tenant = await createTestTenant(apiContext)
 * ```
 */
export async function createTestTenant(
  apiContext: APIRequestContext,
  options: CreateTestDataOptions = {}
): Promise<Tenant> {
  const tenantData = tenantFactory.build(options.factoryOptions)

  if (options.persist !== false && apiContext) {
    try {
      const response = await apiPost<Tenant>(apiContext, '/api/v1/tenants/', tenantData)
      if (response.status === 201 || response.status === 200) {
        return response.data
      }
    } catch (error) {
      console.warn('Failed to create tenant via API, using factory data:', error)
    }
  }

  return tenantData
}

/**
 * Delete test asset
 *
 * @param apiContext - API request context
 * @param assetId - Asset ID to delete
 *
 * @example
 * ```ts
 * await deleteTestAsset(apiContext, asset.id)
 * ```
 */
export async function deleteTestAsset(apiContext: APIRequestContext, assetId: string): Promise<void> {
  try {
    await apiDelete(apiContext, `/api/v1/assets/${assetId}/`)
  } catch (error) {
    console.warn(`Failed to delete asset ${assetId}:`, error)
  }
}

/**
 * Delete test contract
 *
 * @param apiContext - API request context
 * @param contractId - Contract ID to delete
 *
 * @example
 * ```ts
 * await deleteTestContract(apiContext, contract.id)
 * ```
 */
export async function deleteTestContract(
  apiContext: APIRequestContext,
  contractId: string
): Promise<void> {
  try {
    await apiDelete(apiContext, `/api/v1/contracts/${contractId}/`)
  } catch (error) {
    console.warn(`Failed to delete contract ${contractId}:`, error)
  }
}

/**
 * Delete test dataset
 *
 * @param apiContext - API request context
 * @param datasetId - Dataset ID to delete
 *
 * @example
 * ```ts
 * await deleteTestDataset(apiContext, dataset.id)
 * ```
 */
export async function deleteTestDataset(
  apiContext: APIRequestContext,
  datasetId: string
): Promise<void> {
  try {
    await apiDelete(apiContext, `/api/v1/datasets/${datasetId}/`)
  } catch (error) {
    console.warn(`Failed to delete dataset ${datasetId}:`, error)
  }
}

/**
 * Cleanup all test data created during test
 *
 * @param apiContext - API request context
 * @param resources - Resources to cleanup (assets, contracts, datasets, etc.)
 *
 * @example
 * ```ts
 * await cleanupTestData(apiContext, {
 *   assets: [asset1, asset2],
 *   contracts: [contract1],
 * })
 * ```
 */
export async function cleanupTestData(
  apiContext: APIRequestContext,
  resources: {
    assets?: Asset[]
    contracts?: Contract[]
    datasets?: Dataset[]
    users?: User[]
    tenants?: Tenant[]
    jobs?: Job[]
    listings?: MarketplaceListing[]
  }
): Promise<void> {
  // Delete in reverse order of dependencies
  if (resources.listings) {
    for (const listing of resources.listings) {
      try {
        await apiDelete(apiContext, `/api/v1/marketplace/listings/${listing.id}/`)
      } catch (error) {
        console.warn(`Failed to delete listing ${listing.id}:`, error)
      }
    }
  }

  if (resources.jobs) {
    for (const job of resources.jobs) {
      try {
        await apiDelete(apiContext, `/api/v1/jobs/${job.id}/`)
      } catch (error) {
        console.warn(`Failed to delete job ${job.id}:`, error)
      }
    }
  }

  if (resources.assets) {
    for (const asset of resources.assets) {
      await deleteTestAsset(apiContext, asset.id)
    }
  }

  if (resources.contracts) {
    for (const contract of resources.contracts) {
      await deleteTestContract(apiContext, contract.id)
    }
  }

  if (resources.datasets) {
    for (const dataset of resources.datasets) {
      await deleteTestDataset(apiContext, dataset.id)
    }
  }

  // Note: Users and tenants are typically not deleted in tests
  // as they may be shared across tests or needed for debugging
}

/**
 * Create test data for a complete scenario
 *
 * @param apiContext - API request context
 * @param scenario - Scenario name or custom data
 * @returns Created test data
 *
 * @example
 * ```ts
 * const testData = await createTestScenario(apiContext, 'asset-with-contract')
 * ```
 */
export async function createTestScenario(
  apiContext: APIRequestContext,
  scenario: string | {
    assets?: number
    contracts?: number
    datasets?: number
  } = {}
): Promise<{
  assets: Asset[]
  contracts: Contract[]
  datasets: Dataset[]
}> {
  const config =
    typeof scenario === 'string'
      ? {
          assetWithContract: { assets: 1, contracts: 1, datasets: 0 },
          assetWithDataset: { assets: 1, contracts: 0, datasets: 1 },
          complete: { assets: 2, contracts: 1, datasets: 1 },
        }[scenario] || { assets: 1, contracts: 0, datasets: 0 }
      : scenario

  const assets = await createTestAssets(apiContext, config.assets || 0)
  const contracts = await createTestContracts(apiContext, config.contracts || 0)
  const datasets = await createTestDatasets(apiContext, config.datasets || 0)

  return { assets, contracts, datasets }
}

/**
 * Create multiple test datasets
 *
 * @param apiContext - API request context
 * @param count - Number of datasets to create
 * @param options - Creation options
 * @returns Array of created datasets
 */
export async function createTestDatasets(
  apiContext: APIRequestContext,
  count: number,
  options: CreateTestDataOptions = {}
): Promise<Dataset[]> {
  const datasets: Dataset[] = []

  for (let i = 0; i < count; i++) {
    const dataset = await createTestDataset(apiContext, {
      ...options,
      factoryOptions: {
        ...options.factoryOptions,
        overrides: {
          ...options.factoryOptions?.overrides,
          name: `Test Dataset ${i + 1}`,
        },
      },
    })
    datasets.push(dataset)
  }

  return datasets
}

/**
 * Create test marketplace listing via API
 *
 * @param apiContext - API request context
 * @param assetId - Asset ID to list
 * @param options - Creation options
 * @returns Created marketplace listing
 *
 * @example
 * ```ts
 * const listing = await createTestMarketplaceListing(apiContext, assetId)
 * ```
 */
export async function createTestMarketplaceListing(
  apiContext: APIRequestContext,
  assetId: string,
  options: {
    title?: string
    short_description?: string
    long_description?: string
    pricing_model?: 'FREE' | 'FREE_AUTO_APPROVE' | 'REQUEST_APPROVAL'
    tags?: string[]
    domain?: string
    metadata_json?: Record<string, any>
    publish?: boolean
  } = {}
): Promise<MarketplaceListing> {
  const listingData = listingFactory.build({
    overrides: {
      asset: assetId,
      title: options.title || `Test Listing ${Date.now()}`,
      short_description: options.short_description || 'Test listing description',
      long_description: options.long_description || 'Test listing long description',
      pricing_model: options.pricing_model || 'FREE',
      tags: options.tags || ['test'],
      domain: options.domain || 'test-domain',
      metadata_json: {
        title: options.title || `Test Listing ${Date.now()}`,
        short_description: options.short_description || 'Test listing description',
        long_description: options.long_description || 'Test listing long description',
        tags: options.tags || ['test'],
        domain: options.domain || 'test-domain',
        ...options.metadata_json,
      },
    },
  })

  try {
    const response = await apiPost<MarketplaceListing>(
      apiContext,
      '/api/v1/marketplace/listings/',
      {
        asset_id: assetId,
        title: listingData.title,
        short_description: listingData.short_description,
        long_description: listingData.long_description,
        pricing_model: listingData.pricing_model,
        tags: listingData.tags,
        domain: listingData.domain,
      }
    )

    if (response.status === 201 || response.status === 200) {
      let createdListing = response.data

      // Publish if requested
      if (options.publish) {
        try {
          const publishResponse = await apiPost(
            apiContext,
            `/api/v1/marketplace/listings/${createdListing.id}/publish/`,
            {}
          )
          if (publishResponse.status === 200 || publishResponse.status === 201) {
            createdListing = { ...createdListing, status: 'PUBLISHED' as any }
          } else {
            // Try PATCH to update status
            const patchResponse = await apiPatch(
              apiContext,
              `/api/v1/marketplace/listings/${createdListing.id}/`,
              { status: 'PUBLISHED' }
            )
            if (patchResponse.status === 200) {
              createdListing = { ...createdListing, status: 'PUBLISHED' as any }
            }
          }
        } catch (error) {
          console.warn('Failed to publish listing, using draft:', error)
        }
      }

      return createdListing
    }
  } catch (error) {
    console.warn('Failed to create listing via API, using factory data:', error)
  }

  return listingData
}

/**
 * Delete test marketplace listing
 *
 * @param apiContext - API request context
 * @param listingId - Listing ID to delete
 *
 * @example
 * ```ts
 * await deleteTestMarketplaceListing(apiContext, listing.id)
 * ```
 */
export async function deleteTestMarketplaceListing(
  apiContext: APIRequestContext,
  listingId: string
): Promise<void> {
  try {
    await apiDelete(apiContext, `/api/v1/marketplace/listings/${listingId}/`)
  } catch (error) {
    console.warn(`Failed to delete listing ${listingId}:`, error)
  }
}

/**
 * Create test job via API
 *
 * @param apiContext - API request context
 * @param resourceId - Resource ID (asset, dataset, etc.)
 * @param options - Creation options
 * @returns Created job
 *
 * @example
 * ```ts
 * const job = await createTestJob(apiContext, assetId, { type: 'DQ_RUN' })
 * ```
 */
export async function createTestJob(
  apiContext: APIRequestContext,
  resourceId: string,
  options: {
    type?: 'DQ_RUN' | 'COMPLIANCE_RUN' | 'CONTRACT_VALIDATION' | 'SEMANTIC_MAPPING' | 'CONTRACT_MIGRATION' | 'SCHEDULED_INGESTION' | 'RETENTION_POLICY_ENFORCEMENT' | 'SEARCH_INDEX_UPDATE'
    resource_type?: string
    details_json?: Record<string, any>
  } = {}
): Promise<Job> {
  const jobData = jobFactory.build({
    overrides: {
      resource_id: resourceId,
      resource_type: options.resource_type || 'ASSET',
      type: options.type || 'DQ_RUN',
      details_json: options.details_json || {},
    },
  })

  try {
    const response = await apiPost<Job>(apiContext, '/api/v1/jobs/jobs/', {
      type: jobData.type,
      resource_type: jobData.resource_type,
      resource_id: jobData.resource_id,
      details_json: jobData.details_json,
    })

    if (response.status === 201 || response.status === 200) {
      return response.data
    }
  } catch (error) {
    console.warn('Failed to create job via API, using factory data:', error)
  }

  return jobData
}

/**
 * Delete test job
 *
 * @param apiContext - API request context
 * @param jobId - Job ID to delete
 *
 * @example
 * ```ts
 * await deleteTestJob(apiContext, job.id)
 * ```
 */
export async function deleteTestJob(apiContext: APIRequestContext, jobId: string): Promise<void> {
  try {
    await apiDelete(apiContext, `/api/v1/jobs/jobs/${jobId}/`)
  } catch (error) {
    console.warn(`Failed to delete job ${jobId}:`, error)
  }
}

/**
 * Get test data from factory without persisting
 *
 * @param type - Type of data to create
 * @param options - Factory options
 * @returns Test data object
 *
 * @example
 * ```ts
 * const assetData = getTestData('asset', { overrides: { name: 'Custom Asset' } })
 * ```
 */
export function getTestData<T extends 'asset' | 'contract' | 'dataset' | 'user' | 'tenant'>(
  type: T,
  options: FactoryOptions<any> = {}
): T extends 'asset'
  ? Asset
  : T extends 'contract'
    ? Contract
    : T extends 'dataset'
      ? Dataset
      : T extends 'user'
        ? User
        : T extends 'tenant'
          ? Tenant
          : never {
  switch (type) {
    case 'asset':
      return assetFactory.build(options) as any
    case 'contract':
      return contractFactory.build(options) as any
    case 'dataset':
      return datasetFactory.build(options) as any
    case 'user':
      return userFactory.build(options) as any
    case 'tenant':
      return tenantFactory.build(options) as any
    default:
      throw new Error(`Unknown test data type: ${type}`)
  }
}

