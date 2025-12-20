/**
 * Persona-Specific Test Data Factories
 *
 * Factories for creating test data that represents specific user personas
 * and their associated data. These factories create realistic, interconnected
 * test data sets that represent real-world scenarios.
 */

import { assetFactory } from './assetFactory'
import { contractFactory } from './contractFactory'
import { datasetFactory } from './datasetFactory'
import { userFactory } from './userFactory'
import { tenantFactory } from './tenantFactory'
import { jobFactory } from './jobFactory'
import { listingFactory } from './listingFactory'
import type { Asset } from '@/lib/api/assets'
import type { Contract } from '@/lib/api/contracts'
import type { Dataset } from '@/lib/api/datasets'
import type { User } from '@/lib/api/users'
import type { Tenant } from '@/lib/api/tenants'
import type { Job } from '@/lib/api/jobs'
import type { MarketplaceListing } from '@/lib/api/marketplace'

/**
 * Data Producer Persona
 *
 * Represents a user who creates and publishes data assets.
 */
export interface DataProducerPersona {
  user: User
  tenant: Tenant
  assets: Asset[]
  contracts: Contract[]
  datasets: Dataset[]
  listings: MarketplaceListing[]
}

/**
 * Create a Data Producer persona with associated data
 */
export function createDataProducerPersona(): DataProducerPersona {
  const tenant = tenantFactory.active()
  const user = userFactory.active({ overrides: { tenant: tenant.id } })

  // Create assets
  const asset1 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id } })
  const asset2 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id } })

  // Create contracts
  const contract1 = contractFactory.active({ overrides: { asset_id: asset1.id } })
  const contract2 = contractFactory.active({ overrides: { asset_id: asset2.id } })

  // Create datasets
  const dataset1 = datasetFactory.csv({ overrides: { tenant: tenant.id, asset: asset1.id, created_by: user.id } })
  const dataset2 = datasetFactory.json({ overrides: { tenant: tenant.id, asset: asset2.id, created_by: user.id } })

  // Link assets with contracts and datasets
  asset1.contract_id = contract1.id
  asset1.dataset_id = dataset1.id
  asset2.contract_id = contract2.id
  asset2.dataset_id = dataset2.id

  // Create marketplace listings
  const listing1 = listingFactory.published({ overrides: { tenant: tenant.id, asset: asset1.id } })
  const listing2 = listingFactory.published({ overrides: { tenant: tenant.id, asset: asset2.id } })

  return {
    user,
    tenant,
    assets: [asset1, asset2],
    contracts: [contract1, contract2],
    datasets: [dataset1, dataset2],
    listings: [listing1, listing2],
  }
}

/**
 * Data Consumer Persona
 *
 * Represents a user who consumes data from the marketplace.
 */
export interface DataConsumerPersona {
  user: User
  tenant: Tenant
  subscribedAssets: Asset[]
}

/**
 * Create a Data Consumer persona
 */
export function createDataConsumerPersona(availableAssets: Asset[] = []): DataConsumerPersona {
  const tenant = tenantFactory.active()
  const user = userFactory.active({ overrides: { tenant: tenant.id } })

  // Subscribe to some available assets
  const subscribedAssets = availableAssets.slice(0, Math.min(3, availableAssets.length))

  return {
    user,
    tenant,
    subscribedAssets,
  }
}

/**
 * Platform Admin Persona
 *
 * Represents a platform administrator with elevated privileges.
 */
export interface PlatformAdminPersona {
  user: User
  tenants: Tenant[]
  allAssets: Asset[]
  allJobs: Job[]
}

/**
 * Create a Platform Admin persona
 */
export function createPlatformAdminPersona(): PlatformAdminPersona {
  const user = userFactory.platformAdmin({ overrides: { tenant: null } })

  // Create multiple tenants
  const tenant1 = tenantFactory.active()
  const tenant2 = tenantFactory.active()
  const tenant3 = tenantFactory.suspended()

  // Create assets across tenants
  const asset1 = assetFactory.active({ overrides: { tenant: tenant1.id } })
  const asset2 = assetFactory.active({ overrides: { tenant: tenant2.id } })
  const asset3 = assetFactory.active({ overrides: { tenant: tenant3.id } })

  // Create jobs across tenants
  const job1 = jobFactory.completed({ overrides: { tenant: tenant1.id } })
  const job2 = jobFactory.running({ overrides: { tenant: tenant2.id } })
  const job3 = jobFactory.failed({ overrides: { tenant: tenant3.id } })

  return {
    user,
    tenants: [tenant1, tenant2, tenant3],
    allAssets: [asset1, asset2, asset3],
    allJobs: [job1, job2, job3],
  }
}

/**
 * Data Quality Engineer Persona
 *
 * Represents a user focused on data quality and compliance.
 */
export interface DataQualityEngineerPersona {
  user: User
  tenant: Tenant
  assets: Asset[]
  jobs: Job[]
}

/**
 * Create a Data Quality Engineer persona
 */
export function createDataQualityEngineerPersona(): DataQualityEngineerPersona {
  const tenant = tenantFactory.active()
  const user = userFactory.active({ overrides: { tenant: tenant.id } })

  // Create assets with various quality statuses
  const asset1 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id, dq_status: 'PASS' } })
  const asset2 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id, dq_status: 'WARN' } })
  const asset3 = assetFactory.dqFailed({ overrides: { tenant: tenant.id, created_by: user.id } })

  // Create DQ run jobs
  const job1 = jobFactory.completed({
    overrides: {
      tenant: tenant.id,
      type: 'DQ_RUN',
      resource_type: 'ASSET',
      resource_id: asset1.id,
      created_by: user.id,
    }
  })
  const job2 = jobFactory.running({
    overrides: {
      tenant: tenant.id,
      type: 'DQ_RUN',
      resource_type: 'ASSET',
      resource_id: asset2.id,
      created_by: user.id,
    }
  })
  const job3 = jobFactory.failed({
    overrides: {
      tenant: tenant.id,
      type: 'DQ_RUN',
      resource_type: 'ASSET',
      resource_id: asset3.id,
      created_by: user.id,
    }
  })

  return {
    user,
    tenant,
    assets: [asset1, asset2, asset3],
    jobs: [job1, job2, job3],
  }
}

/**
 * Compliance Officer Persona
 *
 * Represents a user focused on compliance and governance.
 */
export interface ComplianceOfficerPersona {
  user: User
  tenant: Tenant
  assets: Asset[]
  contracts: Contract[]
  jobs: Job[]
}

/**
 * Create a Compliance Officer persona
 */
export function createComplianceOfficerPersona(): ComplianceOfficerPersona {
  const tenant = tenantFactory.active()
  const user = userFactory.active({ overrides: { tenant: tenant.id } })

  // Create assets with various compliance statuses
  const asset1 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id, compliance_status: 'PASS' } })
  const asset2 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id, compliance_status: 'WARN' } })
  const asset3 = assetFactory.complianceFailed({ overrides: { tenant: tenant.id, created_by: user.id } })

  // Create contracts with compliance policies
  const contract1 = contractFactory.active({
    overrides: {
      asset_id: asset1.id,
      compliance_policy: {
        contains_personal_data: false,
        jurisdictions: ['US'],
      },
    }
  })
  const contract2 = contractFactory.active({
    overrides: {
      asset_id: asset2.id,
      compliance_policy: {
        contains_personal_data: true,
        jurisdictions: ['EU', 'US'],
        legal_bases: ['CONSENT'],
      },
    }
  })

  // Create compliance run jobs
  const job1 = jobFactory.completed({
    overrides: {
      tenant: tenant.id,
      type: 'COMPLIANCE_RUN',
      resource_type: 'ASSET',
      resource_id: asset1.id,
      created_by: user.id,
    }
  })
  const job2 = jobFactory.completed({
    overrides: {
      tenant: tenant.id,
      type: 'COMPLIANCE_RUN',
      resource_type: 'ASSET',
      resource_id: asset2.id,
      created_by: user.id,
    }
  })
  const job3 = jobFactory.failed({
    overrides: {
      tenant: tenant.id,
      type: 'COMPLIANCE_RUN',
      resource_type: 'ASSET',
      resource_id: asset3.id,
      created_by: user.id,
    }
  })

  return {
    user,
    tenant,
    assets: [asset1, asset2, asset3],
    contracts: [contract1, contract2],
    jobs: [job1, job2, job3],
  }
}

/**
 * Marketplace Publisher Persona
 *
 * Represents a user who publishes assets to the marketplace.
 */
export interface MarketplacePublisherPersona {
  user: User
  tenant: Tenant
  assets: Asset[]
  listings: MarketplaceListing[]
}

/**
 * Create a Marketplace Publisher persona
 */
export function createMarketplacePublisherPersona(): MarketplacePublisherPersona {
  const tenant = tenantFactory.active()
  const user = userFactory.active({ overrides: { tenant: tenant.id } })

  // Create public assets
  const asset1 = assetFactory.public({ overrides: { tenant: tenant.id, created_by: user.id } })
  const asset2 = assetFactory.public({ overrides: { tenant: tenant.id, created_by: user.id } })
  const asset3 = assetFactory.active({ overrides: { tenant: tenant.id, created_by: user.id } }) // Not published

  // Create marketplace listings
  const listing1 = listingFactory.published({
    overrides: {
      tenant: tenant.id,
      asset: asset1.id,
      pricing_model: 'FREE',
    }
  })
  const listing2 = listingFactory.published({
    overrides: {
      tenant: tenant.id,
      asset: asset2.id,
      pricing_model: 'REQUEST_APPROVAL',
      metadata_json: {
        title: 'Premium Data Asset',
        price_amount: 99.99,
        currency: 'USD',
      },
      price_amount: 99.99,
      currency: 'USD',
    }
  })
  const listing3 = listingFactory.draft({
    overrides: {
      tenant: tenant.id,
      asset: asset3.id,
    }
  })

  return {
    user,
    tenant,
    assets: [asset1, asset2, asset3],
    listings: [listing1, listing2, listing3],
  }
}

