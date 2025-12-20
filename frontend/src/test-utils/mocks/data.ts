/**
 * Test Data Factories
 *
 * Factories for creating test data objects.
 * Provides type-safe factories for all major data types.
 */

import type {
  Asset,
  AssetStatus,
  AssetVisibility,
  DQStatus,
  ComplianceStatus,
} from '@/lib/api/assets'
import type {
  Contract,
  ContractStatus,
  NormalizationStatus,
  ValidationStatus,
  HubContractJson,
} from '@/lib/api/contracts'
import type { Job, JobType, JobStatus } from '@/lib/api/jobs'
import type {
  Dataset,
  DatasetFormat,
  DatasetSchema,
  SchemaField,
} from '@/lib/api/datasets'

/**
 * Factory options for creating test data
 */
export interface FactoryOptions {
  /**
   * Override specific fields
   */
  overrides?: Record<string, any>
  /**
   * Generate unique IDs
   * @default true
   */
  uniqueIds?: boolean
}

/**
 * Counter for generating unique IDs
 */
let idCounter = 0

/**
 * Generate a unique ID
 */
function generateId(prefix: string = 'test'): string {
  idCounter++
  return `${prefix}-${idCounter}-${Date.now()}`
}

/**
 * Create a test Asset
 *
 * @param options - Factory options
 * @returns Test Asset object
 *
 * @example
 * ```tsx
 * const asset = createTestAsset()
 * const customAsset = createTestAsset({
 *   overrides: { name: 'Custom Asset', status: 'ACTIVE' }
 * })
 * ```
 */
export function createTestAsset(options: FactoryOptions = {}): Asset {
  const { overrides = {}, uniqueIds = true } = options
  const id = uniqueIds ? generateId('asset') : 'test-asset-1'

  return {
    id,
    tenant: 'test-tenant',
    key: `asset-key-${id}`,
    name: `Test Asset ${id}`,
    description: `Test asset description for ${id}`,
    domain: 'test-domain',
    status: 'ACTIVE' as AssetStatus,
    visibility: 'INTERNAL' as AssetVisibility,
    dq_status: 'PASS' as DQStatus,
    compliance_status: 'PASS' as ComplianceStatus,
    version: 1,
    created_by: 'test-user',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    contract_id: null,
    dataset_id: null,
    contract: null,
    dataset: null,
    ...overrides,
  }
}

/**
 * Create multiple test Assets
 *
 * @param count - Number of assets to create
 * @param options - Factory options
 * @returns Array of test Asset objects
 */
export function createTestAssets(
  count: number,
  options: FactoryOptions = {}
): Asset[] {
  return Array.from({ length: count }, (_, index) =>
    createTestAsset({
      ...options,
      overrides: {
        ...options.overrides,
        name: `Test Asset ${index + 1}`,
      },
    })
  )
}

/**
 * Create a test Contract
 *
 * @param options - Factory options
 * @returns Test Contract object
 */
export function createTestContract(options: FactoryOptions = {}): Contract {
  const { overrides = {}, uniqueIds = true } = options
  const id = uniqueIds ? generateId('contract') : 'test-contract-1'

  const hubContractJson: HubContractJson = {
    hub_contract_version: '1.0.0',
    id,
    info: {
      name: `Test Contract ${id}`,
      owners: [{ name: 'Test Owner', email: 'owner@test.com' }],
      tags: ['test', 'contract'],
    },
    schema: {
      models: [
        {
          name: 'TestModel',
          fields: [
            { name: 'id', type: 'string' },
            { name: 'name', type: 'string' },
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
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    owners: [{ name: 'Test Owner', email: 'owner@test.com' }],
    tags: ['test', 'contract'],
    ...overrides,
  }
}

/**
 * Create multiple test Contracts
 *
 * @param count - Number of contracts to create
 * @param options - Factory options
 * @returns Array of test Contract objects
 */
export function createTestContracts(
  count: number,
  options: FactoryOptions = {}
): Contract[] {
  return Array.from({ length: count }, (_, index) =>
    createTestContract({
      ...options,
      overrides: {
        ...options.overrides,
        hub_contract_json: {
          ...(options.overrides?.hub_contract_json || {}),
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

/**
 * Create a test Job
 *
 * @param options - Factory options
 * @returns Test Job object
 */
export function createTestJob(options: FactoryOptions = {}): Job {
  const { overrides = {}, uniqueIds = true } = options
  const id = uniqueIds ? generateId('job') : 'test-job-1'

  return {
    id,
    tenant: 'test-tenant',
    type: 'DQ_RUN' as JobType,
    status: 'COMPLETED' as JobStatus,
    resource_type: 'ASSET',
    resource_id: 'test-asset-1',
    created_by: 'test-user',
    started_at: new Date(Date.now() - 60000).toISOString(),
    completed_at: new Date().toISOString(),
    error_message: null,
    result_json: { success: true },
    details_json: { progress: 100, current_step: 'Completed' },
    timeout_seconds: 300,
    created_at: new Date(Date.now() - 120000).toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create multiple test Jobs
 *
 * @param count - Number of jobs to create
 * @param options - Factory options
 * @returns Array of test Job objects
 */
export function createTestJobs(
  count: number,
  options: FactoryOptions = {}
): Job[] {
  return Array.from({ length: count }, (_, index) =>
    createTestJob({
      ...options,
      overrides: {
        ...options.overrides,
        type: (['DQ_RUN', 'COMPLIANCE_RUN', 'CONTRACT_VALIDATION'] as JobType[])[
          index % 3
        ],
        status: (['PENDING', 'RUNNING', 'COMPLETED', 'FAILED'] as JobStatus[])[
          index % 4
        ],
      },
    })
  )
}

/**
 * Create a test Dataset
 *
 * @param options - Factory options
 * @returns Test Dataset object
 */
export function createTestDataset(options: FactoryOptions = {}): Dataset {
  const { overrides = {}, uniqueIds = true } = options
  const id = uniqueIds ? generateId('dataset') : 'test-dataset-1'

  const schema: DatasetSchema = {
    fields: [
      { name: 'id', type: 'string', nullable: false },
      { name: 'name', type: 'string', nullable: false },
      { name: 'value', type: 'number', nullable: true },
    ],
  }

  return {
    id,
    tenant: 'test-tenant',
    asset: null,
    file: `test-file-${id}`,
    schema_json: schema,
    sample_data_json: [
      { id: '1', name: 'Test', value: 100 },
      { id: '2', name: 'Test 2', value: 200 },
    ],
    row_count: 1000,
    format: 'CSV' as DatasetFormat,
    version: 1,
    parent_version: null,
    semantic_version: '1.0.0',
    version_tags: ['v1.0.0'],
    is_current: true,
    created_by: 'test-user',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create multiple test Datasets
 *
 * @param count - Number of datasets to create
 * @param options - Factory options
 * @returns Array of test Dataset objects
 */
export function createTestDatasets(
  count: number,
  options: FactoryOptions = {}
): Dataset[] {
  return Array.from({ length: count }, (_, index) =>
    createTestDataset({
      ...options,
      overrides: {
        ...options.overrides,
        format: (['CSV', 'JSON', 'PARQUET'] as DatasetFormat[])[index % 3],
        version: index + 1,
      },
    })
  )
}

/**
 * Create a test User
 */
export function createTestUser(overrides: Record<string, any> = {}) {
  const id = generateId('user')
  return {
    id,
    email: `user-${id}@test.com`,
    username: `user-${id}`,
    first_name: 'Test',
    last_name: 'User',
    is_active: true,
    is_staff: false,
    is_superuser: false,
    date_joined: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Create a test Tenant
 */
export function createTestTenant(overrides: Record<string, any> = {}) {
  const id = generateId('tenant')
  return {
    id,
    name: `Test Tenant ${id}`,
    slug: `test-tenant-${id}`,
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  }
}

/**
 * Reset ID counter (useful for test cleanup)
 */
export function resetIdCounter(): void {
  idCounter = 0
}

