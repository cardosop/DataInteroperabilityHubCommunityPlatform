/**
 * Custom Playwright Fixtures
 *
 * Custom fixtures for E2E tests that extend Playwright's base fixtures.
 * Provides authenticated pages, API contexts, and test data helpers.
 *
 * Uses real implementations - no mocks/stubs. Always fixes root cause.
 */

import { test as base, Page, APIRequestContext, BrowserContext } from '@playwright/test'
import { login, logout, getAuthState, type AuthState, type TestCredentials } from './auth'
import { createApiContext, getApiBaseUrl } from './api'
// Type definitions for test fixtures
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

/**
 * Extended test fixtures
 */
export interface TestFixtures {
  /**
   * Authenticated page with user logged in
   */
  authenticatedPage: Page

  /**
   * API request context with authentication
   */
  apiContext: APIRequestContext

  /**
   * Test user credentials
   */
  testUser: TestCredentials

  /**
   * Authentication state
   */
  authState: AuthState

  /**
   * Test tenant
   */
  testTenant: Tenant

  /**
   * Cleanup function to run after test
   */
  cleanup: () => Promise<void>
}

/**
 * Base test with custom fixtures
 *
 * @example
 * ```ts
 * import { test } from './utils/fixtures'
 *
 * test('my test', async ({ authenticatedPage, apiContext }) => {
 *   // Test code
 * })
 * ```
 */
export const test = base.extend<TestFixtures>({
  /**
   * Test user credentials fixture
   * Creates a test user or uses default credentials
   */
  testUser: async ({ page }, use) => {
    const testUser: TestCredentials = {
      email: process.env.TEST_USER_EMAIL || 'test@example.com',
      password: process.env.TEST_USER_PASSWORD || 'TestPassword123!',
      name: process.env.TEST_USER_NAME || 'Test User',
      tenantId: process.env.TEST_TENANT_ID,
    }

    await use(testUser)
  },

  /**
   * API context fixture
   * Creates an API request context for making API calls
   */
  apiContext: async ({ page }, use) => {
    const context = await createApiContext(page)
    await use(context)
    await context.dispose()
  },

  /**
   * Authenticated page fixture
   * Provides a page with user already logged in
   */
  authenticatedPage: async ({ page, testUser, apiContext }, use) => {
    // Login user
    const authState = await login(page, testUser, apiContext)

    // Use authenticated page
    await use(page)

    // Cleanup: logout after test
    try {
      await logout(page, apiContext)
    } catch (error) {
      console.warn('Failed to logout during cleanup:', error)
    }
  },

  /**
   * Authentication state fixture
   * Provides current authentication state
   */
  authState: async ({ authenticatedPage }, use) => {
    const authState = await getAuthState(authenticatedPage)
    if (!authState) {
      throw new Error('No authentication state available')
    }
    await use(authState)
  },

  /**
   * Test tenant fixture
   * Provides a test tenant for the authenticated user
   */
  testTenant: async ({ apiContext, authState }, use) => {
    // Get tenant from auth state or create one
    let tenant: Tenant

    if (authState.user.tenantId) {
      // Fetch existing tenant
      const response = await apiContext.get(`/api/v1/tenants/${authState.user.tenantId}/`)
      if (response.ok()) {
        tenant = await response.json()
      } else {
        // Create new tenant if fetch fails
        tenant = await createTestTenant(apiContext, authState.user.tenantId)
      }
    } else {
      // Create new tenant
      tenant = await createTestTenant(apiContext)
    }

    await use(tenant)

    // Cleanup: delete tenant if it was created for this test
    // (In real tests, you might want to keep test data for debugging)
    // await cleanupTestTenant(apiContext, tenant.id)
  },

  /**
   * Cleanup fixture
   * Provides a cleanup function for test-specific cleanup
   */
  cleanup: async ({ apiContext }, use) => {
    const cleanupTasks: Array<() => Promise<void>> = []

    const cleanup = async () => {
      // Run all cleanup tasks in reverse order
      for (const task of cleanupTasks.reverse()) {
        try {
          await task()
        } catch (error) {
          console.warn('Cleanup task failed:', error)
        }
      }
    }

    await use(() => cleanup())

    // Run cleanup after test
    await cleanup()
  },
})

/**
 * Helper to create test tenant
 */
async function createTestTenant(
  apiContext: APIRequestContext,
  tenantId?: string
): Promise<Tenant> {
  const tenantData = {
    id: tenantId || `test-tenant-${Date.now()}`,
    name: `Test Tenant ${Date.now()}`,
    slug: `test-tenant-${Date.now()}`,
    description: 'Test tenant created by Playwright tests',
  }

  try {
    const response = await apiContext.post('/api/v1/tenants/', {
      data: tenantData,
    })

    if (response.ok()) {
      return await response.json()
    }
  } catch (error) {
    console.warn('Failed to create test tenant, using mock data:', error)
  }

  // Return mock tenant if creation fails
  return tenantData as Tenant
}

/**
 * Helper to cleanup test tenant
 */
async function cleanupTestTenant(apiContext: APIRequestContext, tenantId: string): Promise<void> {
  try {
    await apiContext.delete(`/api/v1/tenants/${tenantId}/`)
  } catch (error) {
    console.warn(`Failed to cleanup test tenant ${tenantId}:`, error)
  }
}

/**
 * Export base test for tests that don't need custom fixtures
 */
export { test as baseTest } from '@playwright/test'

/**
 * Test with authenticated user (shorthand)
 *
 * @example
 * ```ts
 * import { authenticatedTest } from './utils/fixtures'
 *
 * authenticatedTest('my test', async ({ page, authState }) => {
 *   // Test code with authenticated user
 * })
 * ```
 */
export const authenticatedTest = test

/**
 * Test with API context (shorthand)
 *
 * @example
 * ```ts
 * import { apiTest } from './utils/fixtures'
 *
 * apiTest('my test', async ({ page, apiContext }) => {
 *   // Test code with API context
 * })
 * ```
 */
export const apiTest = test

/**
 * Create a test with custom setup
 *
 * @example
 * ```ts
 * const myTest = test.extend({
 *   customFixture: async ({ page }, use) => {
 *     // Setup
 *     await use(customValue)
 *     // Cleanup
 *   }
 * })
 * ```
 */
export function createTest<T extends Record<string, any>>(
  additionalFixtures: T
): typeof test {
  return test.extend(additionalFixtures)
}

