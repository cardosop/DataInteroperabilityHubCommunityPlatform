/**
 * Tenant Factory
 *
 * Factory for creating test Tenant objects.
 */

import type { Tenant, TenantStatus, KYCStatus } from '@/lib/api/tenants'
import { generateId, generateUUID, randomString, randomDate, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * Tenant factory implementation
 */
class TenantFactory implements FactoryTrait<Tenant> {
  /**
   * Build a single Tenant
   */
  build(options: FactoryOptions<Tenant> = {}): Tenant {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-tenant-1'
    const name = `Test Tenant ${id.substring(0, 8)}`
    const slug = `test-tenant-${id.substring(0, 8).toLowerCase().replace(/-/g, '')}`

    return {
      id,
      name,
      slug,
      status: 'ACTIVE' as TenantStatus,
      kyc_status: 'VERIFIED' as KYCStatus,
      region: 'us-east-1',
      deleted_at: null,
      created_at: randomDate(new Date(Date.now() - 365 * 24 * 60 * 60 * 1000)),
      updated_at: new Date().toISOString(),
      ...overrides,
    }
  }

  buildMany(count: number, options: FactoryOptions<Tenant> = {}): Tenant[] {
    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          name: `Test Tenant ${index + 1}`,
          slug: `test-tenant-${index + 1}`,
        },
      })
    )
  }

  buildSequence(builder: (index: number) => Partial<Tenant>): Tenant[] {
    const tenants: Tenant[] = []
    let index = 0
    let tenant = this.build({ overrides: builder(index) })

    while (tenant) {
      tenants.push(tenant)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      tenant = this.build({ overrides })
    }

    return tenants
  }

  /**
   * Build an ACTIVE tenant
   */
  active(options: FactoryOptions<Tenant> = {}): Tenant {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'ACTIVE' as TenantStatus,
      },
    })
  }

  /**
   * Build a SUSPENDED tenant
   */
  suspended(options: FactoryOptions<Tenant> = {}): Tenant {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'SUSPENDED' as TenantStatus,
      },
    })
  }

  /**
   * Build a DELETED tenant
   */
  deleted(options: FactoryOptions<Tenant> = {}): Tenant {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'DELETED' as TenantStatus,
        deleted_at: new Date().toISOString(),
      },
    })
  }

  /**
   * Build a tenant with UNVERIFIED KYC status
   */
  unverified(options: FactoryOptions<Tenant> = {}): Tenant {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        kyc_status: 'UNVERIFIED' as KYCStatus,
      },
    })
  }

  /**
   * Build a tenant with VERIFIED KYC status
   */
  verified(options: FactoryOptions<Tenant> = {}): Tenant {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        kyc_status: 'VERIFIED' as KYCStatus,
      },
    })
  }

  /**
   * Build a tenant with a specific region
   */
  withRegion(region: string, options: FactoryOptions<Tenant> = {}): Tenant {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        region,
      },
    })
  }
}

export const tenantFactory = new TenantFactory()
export { TenantFactory }

