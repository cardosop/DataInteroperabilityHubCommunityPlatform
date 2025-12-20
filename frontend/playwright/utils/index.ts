/**
 * Playwright Test Utilities
 *
 * Central export for all Playwright test utilities.
 * Import utilities from this file for consistent E2E testing.
 *
 * @example
 * ```ts
 * import { login, apiGet, createTestAsset, BasePage } from './utils'
 * ```
 */

// Authentication helpers
export * from './auth'
export type { TestCredentials, AuthState } from './auth'

// API helpers
export * from './api'
export type { ApiResponse, ApiError } from './api'

// Custom fixtures
export * from './fixtures'
export type { TestFixtures } from './fixtures'

// Test data helpers
export * from './test-data'

// Password reset helpers
export * from './password-reset'
export type {
  PasswordResetRequestResponse,
  PasswordResetConfirmRequest,
  PasswordResetConfirmResponse,
} from './password-reset'

// Page object base class
export { BasePage } from './page-objects'
export type { PageOptions } from './page-objects'

// Test reporting utilities
export * from './test-reporting'
export type { TestResultSummary } from './test-reporting'

// Test dashboard utilities
export * from './test-dashboard'
export type { DashboardConfig } from './test-dashboard'

