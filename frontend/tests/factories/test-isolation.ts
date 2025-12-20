/**
 * Test Database Isolation Configuration
 *
 * Utilities for ensuring test isolation and preventing test data interference.
 * This module provides configuration and utilities for test data namespacing,
 * unique identifiers, and test environment isolation.
 */

import { generateId, generateUUID } from './utils'

/**
 * Test isolation configuration
 */
export interface TestIsolationConfig {
  /**
   * Test run identifier (unique per test run)
   */
  testRunId: string
  /**
   * Test namespace prefix for all test data
   */
  namespacePrefix: string
  /**
   * Whether to use namespaced test data
   * @default true
   */
  useNamespacing: boolean
  /**
   * Test environment identifier
   */
  environment: 'test' | 'integration' | 'e2e'
}

/**
 * Global test isolation configuration
 */
let testIsolationConfig: TestIsolationConfig = {
  testRunId: generateUUID(),
  namespacePrefix: `test-${Date.now()}`,
  useNamespacing: true,
  environment: 'test',
}

/**
 * Initialize test isolation configuration
 *
 * This should be called at the start of each test suite
 * to ensure proper test isolation.
 *
 * @param config - Test isolation configuration
 *
 * @example
 * ```tsx
 * import { initializeTestIsolation } from '@/tests/factories/test-isolation'
 *
 * beforeAll(() => {
 *   initializeTestIsolation({
 *     testRunId: 'my-test-run',
 *     namespacePrefix: 'my-test',
 *     environment: 'integration',
 *   })
 * })
 * ```
 */
export function initializeTestIsolation(config?: Partial<TestIsolationConfig>): void {
  testIsolationConfig = {
    ...testIsolationConfig,
    ...config,
    testRunId: config?.testRunId || generateUUID(),
    namespacePrefix: config?.namespacePrefix || `test-${Date.now()}`,
  }
}

/**
 * Get current test isolation configuration
 */
export function getTestIsolationConfig(): Readonly<TestIsolationConfig> {
  return { ...testIsolationConfig }
}

/**
 * Generate a namespaced identifier
 *
 * This ensures test data has unique identifiers that won't conflict
 * with other test runs or production data.
 *
 * @param baseName - Base name for the identifier
 * @returns Namespaced identifier
 *
 * @example
 * ```tsx
 * const assetKey = generateNamespacedId('asset')
 * // Returns: "test-1234567890-asset-abc123"
 * ```
 */
export function generateNamespacedId(baseName: string): string {
  if (!testIsolationConfig.useNamespacing) {
    return generateId(baseName)
  }

  return `${testIsolationConfig.namespacePrefix}-${baseName}-${generateId('id')}`
}

/**
 * Generate a namespaced key (for assets, contracts, etc.)
 *
 * @param entityType - Type of entity (e.g., 'asset', 'contract')
 * @returns Namespaced key
 */
export function generateNamespacedKey(entityType: string): string {
  return generateNamespacedId(entityType)
}

/**
 * Generate a namespaced name
 *
 * @param entityType - Type of entity
 * @param index - Optional index for uniqueness
 * @returns Namespaced name
 */
export function generateNamespacedName(entityType: string, index?: number): string {
  const base = `${entityType}-${index !== undefined ? index : generateId('name')}`
  return generateNamespacedId(base)
}

/**
 * Check if an identifier belongs to test data
 *
 * @param id - Identifier to check
 * @returns True if identifier appears to be test data
 */
export function isTestDataId(id: string): boolean {
  if (!testIsolationConfig.useNamespacing) {
    // Without namespacing, we can't reliably detect test data
    return false
  }

  return id.startsWith(testIsolationConfig.namespacePrefix) || id.startsWith('test-')
}

/**
 * Reset test isolation configuration
 *
 * This should be called in afterAll hooks to clean up test isolation state.
 */
export function resetTestIsolation(): void {
  testIsolationConfig = {
    testRunId: generateUUID(),
    namespacePrefix: `test-${Date.now()}`,
    useNamespacing: true,
    environment: 'test',
  }
}

/**
 * Create test data with isolation
 *
 * This helper ensures all test data uses proper namespacing.
 *
 * @param factory - Factory function to create test data
 * @param overrides - Overrides for test data
 * @returns Test data with namespaced identifiers
 */
export function createIsolatedTestData<T extends { id?: string; key?: string; name?: string }>(
  factory: () => T,
  overrides?: Partial<T>
): T {
  const data = factory()

  // Apply namespacing
  if (testIsolationConfig.useNamespacing) {
    if (data.id && !overrides?.id) {
      ;(data as any).id = generateNamespacedId('id')
    }
    if (data.key && !overrides?.key) {
      ;(data as any).key = generateNamespacedKey('key')
    }
    if (data.name && !overrides?.name) {
      ;(data as any).name = generateNamespacedName('name')
    }
  }

  // Apply overrides
  return { ...data, ...overrides }
}

/**
 * Test isolation utilities for Vitest
 *
 * Provides hooks for automatic test isolation setup/teardown.
 */
export const testIsolationHooks = {
  /**
   * Setup test isolation (call in beforeAll)
   */
  setup: (config?: Partial<TestIsolationConfig>) => {
    initializeTestIsolation(config)
  },

  /**
   * Teardown test isolation (call in afterAll)
   */
  teardown: () => {
    resetTestIsolation()
  },

  /**
   * Get current test run ID
   */
  getTestRunId: () => testIsolationConfig.testRunId,

  /**
   * Get current namespace prefix
   */
  getNamespacePrefix: () => testIsolationConfig.namespacePrefix,
}

