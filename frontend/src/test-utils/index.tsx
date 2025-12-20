/**
 * Testing Utilities
 *
 * Shared testing utilities and helpers.
 * Export test utilities from this file.
 */

// Re-export everything from @testing-library/react
export * from '@testing-library/react'

// Export renderWithProviders (enhanced render utility)
export { renderWithProviders } from './renderWithProviders'
export type { RenderWithProvidersOptions } from './renderWithProviders'

// Export createTestQueryClient
export {
  createTestQueryClient,
  createTestQueryClientWithCache,
} from './createTestQueryClient'
export type { CreateTestQueryClientOptions } from './createTestQueryClient'

// Export mock API utilities
export * from './mocks/api'

// Export test data factories
export * from './mocks/data'

// Export MSW utilities
export * from './msw'

// Export accessibility testing utilities
export {
  checkAccessibility,
  checkAccessibilityDetailed,
  checkAccessibilityWithRules,
  checkAccessibilityPattern,
  formatAccessibilityViolations,
  assertKeyboardAccessible,
  assertAriaAttributes,
  assertInputHasLabel,
  defaultAxeConfig,
} from './accessibility'

// Export color contrast testing utilities
export {
  calculateContrastRatio,
  meetsWCAGAA,
  meetsWCAGAAA,
  getElementColors,
  checkElementContrast,
} from './color-contrast'
