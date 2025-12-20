/**
 * Test Data Seeding Utilities for E2E Tests
 *
 * Utilities for seeding test data in E2E test environments.
 * These utilities help set up realistic test scenarios for end-to-end testing.
 */

import { assetFactory } from './assetFactory'
import { contractFactory } from './contractFactory'
import { datasetFactory } from './datasetFactory'
import { userFactory } from './userFactory'
import { tenantFactory } from './tenantFactory'
import { jobFactory } from './jobFactory'
import { listingFactory } from './listingFactory'
import { createDataProducerPersona, createDataConsumerPersona, createPlatformAdminPersona } from './personas'
import type { Asset } from '@/lib/api/assets'
import type { Contract } from '@/lib/api/contracts'
import type { Dataset } from '@/lib/api/datasets'
import type { User } from '@/lib/api/users'
import type { Tenant } from '@/lib/api/tenants'
import type { Job } from '@/lib/api/jobs'
import type { MarketplaceListing } from '@/lib/api/marketplace'

/**
 * Seeded test data structure
 */
export interface SeededTestData {
  tenants: Tenant[]
  users: User[]
  assets: Asset[]
  contracts: Contract[]
  datasets: Dataset[]
  jobs: Job[]
  listings: MarketplaceListing[]
}

/**
 * Seeding options
 */
export interface SeedingOptions {
  /**
   * Number of tenants to create
   * @default 3
   */
  tenantCount?: number
  /**
   * Number of users per tenant
   * @default 5
   */
  usersPerTenant?: number
  /**
   * Number of assets per tenant
   * @default 10
   */
  assetsPerTenant?: number
  /**
   * Number of contracts per tenant
   * @default 8
   */
  contractsPerTenant?: number
  /**
   * Number of datasets per tenant
   * @default 10
   */
  datasetsPerTenant?: number
  /**
   * Number of jobs per tenant
   * @default 15
   */
  jobsPerTenant?: number
  /**
   * Number of marketplace listings per tenant
   * @default 5
   */
  listingsPerTenant?: number
  /**
   * Include platform admin
   * @default true
   */
  includePlatformAdmin?: boolean
}

/**
 * Seed comprehensive test data for E2E tests
 *
 * This function creates a realistic test data set that can be used
 * for end-to-end testing scenarios.
 *
 * @param options - Seeding options
 * @returns Seeded test data
 *
 * @example
 * ```tsx
 * import { seedTestData } from '@/tests/factories/seeding'
 *
 * beforeAll(async () => {
 *   const testData = await seedTestData({
 *     tenantCount: 2,
 *     assetsPerTenant: 5,
 *   })
 *   // Use testData in tests
 * })
 * ```
 */
export async function seedTestData(options: SeedingOptions = {}): Promise<SeededTestData> {
  const {
    tenantCount = 3,
    usersPerTenant = 5,
    assetsPerTenant = 10,
    contractsPerTenant = 8,
    datasetsPerTenant = 10,
    jobsPerTenant = 15,
    listingsPerTenant = 5,
    includePlatformAdmin = true,
  } = options

  const seeded: SeededTestData = {
    tenants: [],
    users: [],
    assets: [],
    contracts: [],
    datasets: [],
    jobs: [],
    listings: [],
  }

  // Create tenants
  for (let i = 0; i < tenantCount; i++) {
    const tenant = tenantFactory.active()
    seeded.tenants.push(tenant)

    // Create users for this tenant
    for (let j = 0; j < usersPerTenant; j++) {
      const user = userFactory.active({ overrides: { tenant: tenant.id } })
      seeded.users.push(user)
    }

    // Create assets for this tenant
    for (let j = 0; j < assetsPerTenant; j++) {
      const user = seeded.users[Math.floor(Math.random() * seeded.users.length)]
      const asset = assetFactory.build({
        overrides: {
          tenant: tenant.id,
          created_by: user.id,
          status: j % 3 === 0 ? 'DRAFT' : j % 3 === 1 ? 'ACTIVE' : 'PUBLIC',
        },
      })
      seeded.assets.push(asset)
    }

    // Create contracts for this tenant
    for (let j = 0; j < contractsPerTenant; j++) {
      const asset = seeded.assets[Math.floor(Math.random() * seeded.assets.length)]
      const contract = contractFactory.build({
        overrides: {
          asset_id: asset.id,
          status: j % 2 === 0 ? 'ACTIVE' : 'DRAFT',
        },
      })
      seeded.contracts.push(contract)
    }

    // Create datasets for this tenant
    for (let j = 0; j < datasetsPerTenant; j++) {
      const user = seeded.users[Math.floor(Math.random() * seeded.users.length)]
      const asset = seeded.assets[Math.floor(Math.random() * seeded.assets.length)]
      const dataset = datasetFactory.build({
        overrides: {
          tenant: tenant.id,
          asset: asset.id,
          created_by: user.id,
          format: j % 3 === 0 ? 'CSV' : j % 3 === 1 ? 'JSON' : 'PARQUET',
        },
      })
      seeded.datasets.push(dataset)
    }

    // Create jobs for this tenant
    for (let j = 0; j < jobsPerTenant; j++) {
      const user = seeded.users[Math.floor(Math.random() * seeded.users.length)]
      const asset = seeded.assets[Math.floor(Math.random() * seeded.assets.length)]
      const jobTypes: Array<'DQ_RUN' | 'COMPLIANCE_RUN' | 'CONTRACT_VALIDATION'> = [
        'DQ_RUN',
        'COMPLIANCE_RUN',
        'CONTRACT_VALIDATION',
      ]
      const jobStatuses: Array<'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'> = [
        'PENDING',
        'RUNNING',
        'COMPLETED',
        'FAILED',
      ]
      const job = jobFactory.build({
        overrides: {
          tenant: tenant.id,
          type: jobTypes[j % jobTypes.length],
          status: jobStatuses[j % jobStatuses.length],
          resource_type: 'ASSET',
          resource_id: asset.id,
          created_by: user.id,
        },
      })
      seeded.jobs.push(job)
    }

    // Create marketplace listings for this tenant
    for (let j = 0; j < listingsPerTenant; j++) {
      const asset = seeded.assets[Math.floor(Math.random() * seeded.assets.length)]
      const listing = listingFactory.build({
        overrides: {
          tenant: tenant.id,
          asset: asset.id,
          status: j % 2 === 0 ? 'PUBLISHED' : 'DRAFT',
        },
      })
      seeded.listings.push(listing)
    }
  }

  // Create platform admin if requested
  if (includePlatformAdmin) {
    const admin = userFactory.platformAdmin({ overrides: { tenant: null } })
    seeded.users.push(admin)
  }

  return seeded
}

/**
 * Seed minimal test data (quick setup for simple tests)
 */
export async function seedMinimalTestData(): Promise<SeededTestData> {
  return seedTestData({
    tenantCount: 1,
    usersPerTenant: 2,
    assetsPerTenant: 3,
    contractsPerTenant: 2,
    datasetsPerTenant: 3,
    jobsPerTenant: 5,
    listingsPerTenant: 2,
    includePlatformAdmin: false,
  })
}

/**
 * Seed test data for a specific persona
 */
export async function seedPersonaTestData(
  persona: 'dataProducer' | 'dataConsumer' | 'platformAdmin' | 'dataQualityEngineer' | 'complianceOfficer' | 'marketplacePublisher'
): Promise<SeededTestData> {
  switch (persona) {
    case 'dataProducer': {
      const personaData = createDataProducerPersona()
      return {
        tenants: [personaData.tenant],
        users: [personaData.user],
        assets: personaData.assets,
        contracts: personaData.contracts,
        datasets: personaData.datasets,
        jobs: [],
        listings: personaData.listings,
      }
    }
    case 'dataConsumer': {
      const producer = createDataProducerPersona()
      const personaData = createDataConsumerPersona(producer.assets)
      return {
        tenants: [producer.tenant, personaData.tenant],
        users: [producer.user, personaData.user],
        assets: producer.assets,
        contracts: producer.contracts,
        datasets: producer.datasets,
        jobs: [],
        listings: producer.listings,
      }
    }
    case 'platformAdmin': {
      const personaData = createPlatformAdminPersona()
      return {
        tenants: personaData.tenants,
        users: [personaData.user],
        assets: personaData.allAssets,
        contracts: [],
        datasets: [],
        jobs: personaData.allJobs,
        listings: [],
      }
    }
    default:
      return seedMinimalTestData()
  }
}

