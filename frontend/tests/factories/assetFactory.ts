/**
 * Asset Factory
 *
 * Factory for creating test Asset objects.
 */

import type {
  Asset,
  AssetStatus,
  AssetVisibility,
  DQStatus,
  ComplianceStatus,
} from '@/lib/api/assets'
import { generateId, generateUUID, randomDate, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * Asset factory implementation
 */
class AssetFactory implements FactoryTrait<Asset> {
  /**
   * Build a single Asset
   *
   * @param options - Factory options
   * @returns Test Asset object
   *
   * @example
   * ```tsx
   * const asset = assetFactory.build()
   * const customAsset = assetFactory.build({
   *   overrides: { name: 'Custom Asset', status: 'ACTIVE' }
   * })
   * ```
   */
  build(options: FactoryOptions<Asset> = {}): Asset {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-asset-1'
    const now = new Date().toISOString()

    return {
      id,
      tenant: 'test-tenant',
      key: `asset-key-${id.substring(0, 8)}`,
      name: `Test Asset ${id.substring(0, 8)}`,
      description: `Test asset description for ${id.substring(0, 8)}`,
      domain: 'test-domain',
      status: 'ACTIVE' as AssetStatus,
      visibility: 'INTERNAL' as AssetVisibility,
      dq_status: 'PASS' as DQStatus,
      compliance_status: 'PASS' as ComplianceStatus,
      version: 1,
      created_by: 'test-user',
      created_at: randomDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)),
      updated_at: now,
      contract_id: null,
      dataset_id: null,
      contract: null,
      dataset: null,
      ...overrides,
    }
  }

  /**
   * Build multiple Assets
   *
   * @param count - Number of assets to create
   * @param options - Factory options
   * @returns Array of test Asset objects
   */
  buildMany(count: number, options: FactoryOptions<Asset> = {}): Asset[] {
    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          name: `Test Asset ${index + 1}`,
        },
      })
    )
  }

  /**
   * Build a sequence with custom builder function
   *
   * @param builder - Function that receives index and returns partial Asset
   * @returns Array of test Asset objects
   */
  buildSequence(builder: (index: number) => Partial<Asset>): Asset[] {
    const assets: Asset[] = []
    let index = 0
    let asset = this.build({ overrides: builder(index) })

    while (asset) {
      assets.push(asset)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      asset = this.build({ overrides })
    }

    return assets
  }

  /**
   * Build an Asset with DRAFT status
   */
  draft(options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'DRAFT' as AssetStatus,
      },
    })
  }

  /**
   * Build an Asset with ACTIVE status
   */
  active(options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'ACTIVE' as AssetStatus,
      },
    })
  }

  /**
   * Build an Asset with PUBLIC visibility
   */
  public(options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        visibility: 'PUBLIC' as AssetVisibility,
        status: 'PUBLIC' as AssetStatus,
      },
    })
  }

  /**
   * Build an Asset with FAILED compliance status
   */
  complianceFailed(options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        compliance_status: 'FAIL' as ComplianceStatus,
      },
    })
  }

  /**
   * Build an Asset with FAILED data quality status
   */
  dqFailed(options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        dq_status: 'FAIL' as DQStatus,
      },
    })
  }

  /**
   * Build an Asset with a contract
   */
  withContract(contractId: string, options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        contract_id: contractId,
        contract: {
          id: contractId,
          name: 'Test Contract',
          status: 'ACTIVE',
        },
      },
    })
  }

  /**
   * Build an Asset with a dataset
   */
  withDataset(datasetId: string, options: FactoryOptions<Asset> = {}): Asset {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        dataset_id: datasetId,
        dataset: {
          id: datasetId,
          name: 'Test Dataset',
          format: 'CSV',
        },
      },
    })
  }
}

/**
 * Export singleton instance
 */
export const assetFactory = new AssetFactory()

/**
 * Export factory class for advanced usage
 */
export { AssetFactory }

