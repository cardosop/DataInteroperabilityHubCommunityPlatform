/**
 * API-Based Test Data Seeding Utilities
 *
 * Utilities for seeding test data via real API calls (no mocks/stubs).
 * These utilities create actual test data in the API server for integration tests.
 */

import { createAsset, type CreateAssetRequest, type Asset } from '@/lib/api/assets'
import { createContract, type CreateContractRequest, type Contract } from '@/lib/api/contracts'
import { createDataset, type CreateDatasetRequest, type Dataset } from '@/lib/api/datasets'
import { assetFactory } from './assetFactory'
import { contractFactory } from './contractFactory'
import { datasetFactory } from './datasetFactory'
import { testDataRegistry } from './cleanup'
import type { AxiosError } from 'axios'

/**
 * API-based seeded test data structure
 */
export interface ApiSeededTestData {
  assets: Asset[]
  contracts: Contract[]
  datasets: Dataset[]
}

/**
 * API seeding options
 */
export interface ApiSeedingOptions {
  /**
   * Number of assets to create
   * @default 5
   */
  assetCount?: number
  /**
   * Number of contracts to create
   * @default 3
   */
  contractCount?: number
  /**
   * Number of datasets to create
   * @default 5
   */
  datasetCount?: number
  /**
   * Asset ID to associate contracts/datasets with
   */
  assetId?: string
  /**
   * Continue on error (don't throw if some creations fail)
   * @default true
   */
  continueOnError?: boolean
}

/**
 * Seed test data via API calls
 *
 * This function creates actual test data in the API server.
 * All created data is automatically registered for cleanup.
 *
 * @param options - Seeding options
 * @returns Seeded test data with actual API responses
 *
 * @example
 * ```tsx
 * import { seedTestDataViaAPI } from '@/tests/factories/api-seeding'
 *
 * beforeAll(async () => {
 *   const testData = await seedTestDataViaAPI({
 *     assetCount: 5,
 *     contractCount: 3,
 *   })
 *   // Use testData.assets, testData.contracts in tests
 * })
 * ```
 */
export async function seedTestDataViaAPI(
  options: ApiSeedingOptions = {}
): Promise<ApiSeededTestData> {
  const {
    assetCount = 5,
    contractCount = 3,
    datasetCount = 5,
    assetId,
    continueOnError = true,
  } = options

  const seeded: ApiSeededTestData = {
    assets: [],
    contracts: [],
    datasets: [],
  }

  const errors: Array<{ type: string; error: string }> = []

  // Create assets
  for (let i = 0; i < assetCount; i++) {
    try {
      const assetData = assetFactory.build()
      const createData: CreateAssetRequest = {
        key: assetData.key,
        name: assetData.name,
        description: assetData.description || undefined,
        domain: assetData.domain || undefined,
        visibility: assetData.visibility,
      }

      const asset = await createAsset(createData)
      seeded.assets.push(asset)
      testDataRegistry.registerAsset(asset.id)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      errors.push({ type: 'asset', error: errorMessage })
      if (!continueOnError) {
        throw error
      }
      console.warn(`[Test Seeding] Failed to create asset ${i + 1}:`, errorMessage)
    }
  }

  // Use provided assetId or first created asset
  const targetAssetId = assetId || seeded.assets[0]?.id

  // Create contracts
  if (targetAssetId) {
    for (let i = 0; i < contractCount; i++) {
      try {
        const contractData = contractFactory.build()
        const createData: CreateContractRequest = {
          original_raw: JSON.stringify(contractData.hub_contract_json),
          original_format: 'JSON',
          asset_id: targetAssetId,
          name: contractData.hub_contract_json.info?.name || `Test Contract ${i + 1}`,
        }

        const contract = await createContract(createData)
        seeded.contracts.push(contract)
        testDataRegistry.registerContract(contract.id)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error)
        errors.push({ type: 'contract', error: errorMessage })
        if (!continueOnError) {
          throw error
        }
        console.warn(`[Test Seeding] Failed to create contract ${i + 1}:`, errorMessage)
      }
    }
  }

  // Create datasets (requires file upload - simplified for now)
  // Note: Full dataset creation requires file upload, which is complex
  // This is a placeholder that shows the pattern
  if (targetAssetId) {
    console.warn(
      '[Test Seeding] Dataset creation requires file upload. Skipping dataset seeding.'
    )
  }

  if (errors.length > 0) {
    console.warn(`[Test Seeding] Completed with ${errors.length} errors:`, errors)
  }

  return seeded
}

/**
 * Seed minimal test data via API (quick setup)
 */
export async function seedMinimalTestDataViaAPI(): Promise<ApiSeededTestData> {
  return seedTestDataViaAPI({
    assetCount: 2,
    contractCount: 1,
    datasetCount: 0, // Skip datasets as they require file upload
  })
}

/**
 * Seed a single asset via API
 */
export async function seedSingleAssetViaAPI(
  overrides?: Partial<CreateAssetRequest>
): Promise<Asset> {
  const assetData = assetFactory.build()
  const createData: CreateAssetRequest = {
    key: assetData.key,
    name: assetData.name,
    description: assetData.description || undefined,
    domain: assetData.domain || undefined,
    visibility: assetData.visibility,
    ...overrides,
  }

  const asset = await createAsset(createData)
  testDataRegistry.registerAsset(asset.id)
  return asset
}

/**
 * Seed a single contract via API
 */
export async function seedSingleContractViaAPI(
  assetId: string,
  overrides?: Partial<CreateContractRequest>
): Promise<Contract> {
  const contractData = contractFactory.build()
  const createData: CreateContractRequest = {
    original_raw: JSON.stringify(contractData.hub_contract_json),
    original_format: 'JSON',
    asset_id: assetId,
    name: contractData.hub_contract_json.info?.name || 'Test Contract',
    ...overrides,
  }

  const contract = await createContract(createData)
  testDataRegistry.registerContract(contract.id)
  return contract
}

