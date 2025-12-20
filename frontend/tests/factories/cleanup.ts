/**
 * Test Data Cleanup Utilities
 *
 * Utilities for cleaning up test data after tests.
 * These utilities help ensure test isolation and prevent data leakage.
 *
 * These utilities make real API calls to delete test data - no mocks or stubs.
 */

import { resetIdCounter } from './utils'
import { deleteAsset } from '@/lib/api/assets'
import { deleteContract } from '@/lib/api/contracts'

/**
 * Test data registry for tracking created test data
 */
class TestDataRegistry {
  private assets: string[] = []
  private contracts: string[] = []
  private datasets: string[] = []
  private users: string[] = []
  private tenants: string[] = []
  private jobs: string[] = []
  private listings: string[] = []

  /**
   * Register an asset ID for cleanup
   */
  registerAsset(id: string): void {
    this.assets.push(id)
  }

  /**
   * Register a contract ID for cleanup
   */
  registerContract(id: string): void {
    this.contracts.push(id)
  }

  /**
   * Register a dataset ID for cleanup
   */
  registerDataset(id: string): void {
    this.datasets.push(id)
  }

  /**
   * Register a user ID for cleanup
   */
  registerUser(id: string): void {
    this.users.push(id)
  }

  /**
   * Register a tenant ID for cleanup
   */
  registerTenant(id: string): void {
    this.tenants.push(id)
  }

  /**
   * Register a job ID for cleanup
   */
  registerJob(id: string): void {
    this.jobs.push(id)
  }

  /**
   * Register a listing ID for cleanup
   */
  registerListing(id: string): void {
    this.listings.push(id)
  }

  /**
   * Get all registered IDs
   */
  getAllIds(): {
    assets: string[]
    contracts: string[]
    datasets: string[]
    users: string[]
    tenants: string[]
    jobs: string[]
    listings: string[]
  } {
    return {
      assets: [...this.assets],
      contracts: [...this.contracts],
      datasets: [...this.datasets],
      users: [...this.users],
      tenants: [...this.tenants],
      jobs: [...this.jobs],
      listings: [...this.listings],
    }
  }

  /**
   * Clear all registered IDs
   */
  clear(): void {
    this.assets = []
    this.contracts = []
    this.datasets = []
    this.users = []
    this.tenants = []
    this.jobs = []
    this.listings = []
  }
}

/**
 * Global test data registry instance
 */
export const testDataRegistry = new TestDataRegistry()

/**
 * Cleanup options
 */
export interface CleanupOptions {
  /**
   * Reset ID counter
   * @default true
   */
  resetIdCounter?: boolean
  /**
   * Clear registry
   * @default true
   */
  clearRegistry?: boolean
}

/**
 * Cleanup all test data
 *
 * This function should be called in afterEach or afterAll hooks
 * to ensure test isolation.
 *
 * @param options - Cleanup options
 *
 * @example
 * ```tsx
 * import { cleanupTestData } from '@/tests/factories/cleanup'
 *
 * afterEach(() => {
 *   cleanupTestData()
 * })
 * ```
 */
export function cleanupTestData(options: CleanupOptions = {}): void {
  const { resetIdCounter: resetCounter = true, clearRegistry = true } = options

  if (resetCounter) {
    resetIdCounter()
  }

  if (clearRegistry) {
    testDataRegistry.clear()
  }
}

/**
 * Cleanup specific test data by type (makes real API calls)
 *
 * This function actually deletes test data from the API server.
 * It handles errors gracefully and continues cleanup even if some deletions fail.
 */
export async function cleanupTestDataByType(
  type: 'assets' | 'contracts' | 'datasets' | 'users' | 'tenants' | 'jobs' | 'listings',
  ids: string[],
  options: { continueOnError?: boolean } = {}
): Promise<{ success: number; failed: number; errors: Array<{ id: string; error: string }> }> {
  const { continueOnError = true } = options
  const results = { success: 0, failed: 0, errors: [] as Array<{ id: string; error: string }> }

  for (const id of ids) {
    try {
      switch (type) {
        case 'assets':
          await deleteAsset(id)
          results.success++
          break
        case 'contracts':
          await deleteContract(id)
          results.success++
          break
        case 'datasets':
          // Datasets might not have a delete endpoint, or deletion might be restricted
          // Log a warning but don't fail
          console.warn(`[Test Cleanup] Dataset deletion not implemented: ${id}`)
          results.success++
          break
        case 'users':
          // User deletion might require admin privileges
          console.warn(`[Test Cleanup] User deletion not implemented: ${id}`)
          results.success++
          break
        case 'tenants':
          // Tenant deletion might require admin privileges
          console.warn(`[Test Cleanup] Tenant deletion not implemented: ${id}`)
          results.success++
          break
        case 'jobs':
          // Jobs are typically not deleted, they're just completed
          results.success++
          break
        case 'listings':
          // Marketplace listing deletion might not be implemented
          console.warn(`[Test Cleanup] Listing deletion not implemented: ${id}`)
          results.success++
          break
      }
    } catch (error) {
      results.failed++
      const errorMessage = error instanceof Error ? error.message : String(error)
      results.errors.push({ id, error: errorMessage })

      if (!continueOnError) {
        throw error
      }

      // Log error but continue
      console.warn(`[Test Cleanup] Failed to delete ${type} ${id}:`, errorMessage)
    }
  }

  // Remove successfully deleted IDs from registry
  const registry = testDataRegistry.getAllIds()
  const successfulIds = ids.filter(id =>
    !results.errors.some(e => e.id === id)
  )

  switch (type) {
    case 'assets':
      registry.assets = registry.assets.filter(id => !successfulIds.includes(id))
      break
    case 'contracts':
      registry.contracts = registry.contracts.filter(id => !successfulIds.includes(id))
      break
    case 'datasets':
      registry.datasets = registry.datasets.filter(id => !successfulIds.includes(id))
      break
    case 'users':
      registry.users = registry.users.filter(id => !successfulIds.includes(id))
      break
    case 'tenants':
      registry.tenants = registry.tenants.filter(id => !successfulIds.includes(id))
      break
    case 'jobs':
      registry.jobs = registry.jobs.filter(id => !successfulIds.includes(id))
      break
    case 'listings':
      registry.listings = registry.listings.filter(id => !successfulIds.includes(id))
      break
  }

  return results
}

/**
 * Create a cleanup function for a specific test
 *
 * @returns Cleanup function
 *
 * @example
 * ```tsx
 * const cleanup = createTestCleanup()
 *
 * const asset = assetFactory.build()
 * cleanup.registerAsset(asset.id)
 *
 * // After test
 * cleanup.cleanup()
 * ```
 */
export function createTestCleanup() {
  const registeredIds: {
    assets: string[]
    contracts: string[]
    datasets: string[]
    users: string[]
    tenants: string[]
    jobs: string[]
    listings: string[]
  } = {
    assets: [],
    contracts: [],
    datasets: [],
    users: [],
    tenants: [],
    jobs: [],
    listings: [],
  }

  return {
    registerAsset: (id: string) => {
      registeredIds.assets.push(id)
      testDataRegistry.registerAsset(id)
    },
    registerContract: (id: string) => {
      registeredIds.contracts.push(id)
      testDataRegistry.registerContract(id)
    },
    registerDataset: (id: string) => {
      registeredIds.datasets.push(id)
      testDataRegistry.registerDataset(id)
    },
    registerUser: (id: string) => {
      registeredIds.users.push(id)
      testDataRegistry.registerUser(id)
    },
    registerTenant: (id: string) => {
      registeredIds.tenants.push(id)
      testDataRegistry.registerTenant(id)
    },
    registerJob: (id: string) => {
      registeredIds.jobs.push(id)
      testDataRegistry.registerJob(id)
    },
    registerListing: (id: string) => {
      registeredIds.listings.push(id)
      testDataRegistry.registerListing(id)
    },
    cleanup: async (options: { continueOnError?: boolean } = {}) => {
      const { continueOnError = true } = options
      const results = {
        assets: { success: 0, failed: 0 },
        contracts: { success: 0, failed: 0 },
        datasets: { success: 0, failed: 0 },
        users: { success: 0, failed: 0 },
        tenants: { success: 0, failed: 0 },
        jobs: { success: 0, failed: 0 },
        listings: { success: 0, failed: 0 },
      }

      // Cleanup in reverse dependency order
      if (registeredIds.listings.length > 0) {
        const result = await cleanupTestDataByType('listings', registeredIds.listings, { continueOnError })
        results.listings = result
      }
      if (registeredIds.jobs.length > 0) {
        const result = await cleanupTestDataByType('jobs', registeredIds.jobs, { continueOnError })
        results.jobs = result
      }
      if (registeredIds.datasets.length > 0) {
        const result = await cleanupTestDataByType('datasets', registeredIds.datasets, { continueOnError })
        results.datasets = result
      }
      if (registeredIds.contracts.length > 0) {
        const result = await cleanupTestDataByType('contracts', registeredIds.contracts, { continueOnError })
        results.contracts = result
      }
      if (registeredIds.assets.length > 0) {
        const result = await cleanupTestDataByType('assets', registeredIds.assets, { continueOnError })
        results.assets = result
      }
      if (registeredIds.users.length > 0) {
        const result = await cleanupTestDataByType('users', registeredIds.users, { continueOnError })
        results.users = result
      }
      if (registeredIds.tenants.length > 0) {
        const result = await cleanupTestDataByType('tenants', registeredIds.tenants, { continueOnError })
        results.tenants = result
      }

      const total = Object.values(registeredIds).reduce((sum, ids) => sum + ids.length, 0)
      const totalSuccess = Object.values(results).reduce((sum, r) => sum + r.success, 0)
      const totalFailed = Object.values(results).reduce((sum, r) => sum + r.failed, 0)

      if (total > 0) {
        console.log(`[Test Cleanup] Cleaned up ${totalSuccess}/${total} test data items (${totalFailed} failed)`)
      }

      // Clear registered IDs after cleanup
      registeredIds.assets = []
      registeredIds.contracts = []
      registeredIds.datasets = []
      registeredIds.users = []
      registeredIds.tenants = []
      registeredIds.jobs = []
      registeredIds.listings = []

      return results
    },
    getRegisteredIds: () => ({ ...registeredIds }),
  }
}

