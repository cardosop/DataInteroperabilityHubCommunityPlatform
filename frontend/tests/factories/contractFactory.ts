/**
 * Contract Factory
 *
 * Factory for creating test Contract objects.
 */

import type {
  Contract,
  ContractStatus,
  NormalizationStatus,
  ValidationStatus,
  HubContractJson,
} from '@/lib/api/contracts'
import { generateId, generateUUID, randomDate, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * Contract factory implementation
 */
class ContractFactory implements FactoryTrait<Contract> {
  /**
   * Build a single Contract
   */
  build(options: FactoryOptions<Contract> = {}): Contract {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-contract-1'
    const now = new Date().toISOString()

    const hubContractJson: HubContractJson = {
      hub_contract_version: '1.0.0',
      id,
      info: {
        name: `Test Contract ${id.substring(0, 8)}`,
        description: `Test contract description for ${id.substring(0, 8)}`,
        version: '1.0.0',
        owners: [{ name: 'Test Owner', email: 'owner@test.com' }],
        tags: ['test', 'contract'],
        domain: 'test-domain',
        status: 'ACTIVE',
      },
      schema: {
        models: [
          {
            name: 'TestModel',
            fields: [
              { name: 'id', type: 'string', required: true },
              { name: 'name', type: 'string', required: true },
              { name: 'value', type: 'number', required: false },
            ],
          },
        ],
      },
    }

    return {
      id,
      hub_contract_json: hubContractJson,
      status: 'ACTIVE' as ContractStatus,
      normalization_status: 'NORMALIZED_OK' as NormalizationStatus,
      validation_status: 'VALID' as ValidationStatus,
      original_raw: null,
      original_format: null,
      original_spec_type: null,
      asset_id: null,
      created_at: randomDate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)),
      updated_at: now,
      owners: [{ name: 'Test Owner', email: 'owner@test.com' }],
      tags: ['test', 'contract'],
      quality_rules: [],
      compliance_policy: {},
      lifecycle_policy: {},
      marketplace_policy: {},
      schema_fields: [
        { name: 'id', type: 'string' },
        { name: 'name', type: 'string' },
      ],
      ...overrides,
    }
  }

  buildMany(count: number, options: FactoryOptions<Contract> = {}): Contract[] {
    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          hub_contract_json: {
            ...(options.overrides?.hub_contract_json as HubContractJson | undefined),
            info: {
              name: `Test Contract ${index + 1}`,
              owners: [{ name: 'Test Owner', email: 'owner@test.com' }],
              tags: ['test', 'contract'],
            },
          },
        },
      })
    )
  }

  buildSequence(builder: (index: number) => Partial<Contract>): Contract[] {
    const contracts: Contract[] = []
    let index = 0
    let contract = this.build({ overrides: builder(index) })

    while (contract) {
      contracts.push(contract)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      contract = this.build({ overrides })
    }

    return contracts
  }

  /**
   * Build a Contract with DRAFT status
   */
  draft(options: FactoryOptions<Contract> = {}): Contract {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'DRAFT' as ContractStatus,
      },
    })
  }

  /**
   * Build a Contract with INVALID validation status
   */
  invalid(options: FactoryOptions<Contract> = {}): Contract {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        validation_status: 'INVALID' as ValidationStatus,
      },
    })
  }

  /**
   * Build a Contract with WARNING_ONLY validation status
   */
  warning(options: FactoryOptions<Contract> = {}): Contract {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        validation_status: 'WARNING_ONLY' as ValidationStatus,
      },
    })
  }

  /**
   * Build a Contract with an asset
   */
  withAsset(assetId: string, options: FactoryOptions<Contract> = {}): Contract {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        asset_id: assetId,
      },
    })
  }
}

export const contractFactory = new ContractFactory()
export { ContractFactory }

