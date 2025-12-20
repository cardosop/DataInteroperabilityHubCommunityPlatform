/**
 * Accessibility Testing Utilities
 *
 * Comprehensive utilities for testing accessibility with axe-core.
 * Uses @axe-core/react and vitest-axe for Vitest compatibility.
 *
 * @example
 * ```tsx
 * import { render } from '@/test-utils'
 * import { checkAccessibility } from '@/test-utils/accessibility'
 * import { Button } from './Button'
 *
 * it('has no accessibility violations', async () => {
 *   const { container } = render(<Button>Click me</Button>)
 *   await checkAccessibility(container)
 * })
 * ```
 */

import { expect } from 'vitest'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import 'vitest-axe/extend-expect'
import type { AxeResults } from 'axe-core'

// Extend Vitest's expect with axe matchers
expect.extend(matchers)

/**
 * Default axe configuration
 * Follows WCAG 2.1 Level AA standards
 */
export const defaultAxeConfig = {
  // Use tags to enable WCAG 2.1 Level AA rules instead of manually listing rules
  // This ensures we use valid axe-core rules
  tags: ['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'],
  // Only disable specific rules if needed, don't enable invalid ones
  rules: {
    // Disable rules that might be too strict for testing
    // 'color-contrast': { enabled: false }, // Can be flaky in tests
  },
}

/**
 * Check accessibility of a container element
 *
 * @param container - The container element to test
 * @param config - Optional axe configuration
 * @returns Promise that resolves when accessibility check is complete
 *
 * @example
 * ```tsx
 * const { container } = render(<MyComponent />)
 * await checkAccessibility(container)
 * ```
 */
export async function checkAccessibility(
  container: HTMLElement,
  config: typeof defaultAxeConfig = defaultAxeConfig
): Promise<void> {
  const results = await axe(container, config)
  expect(results).toHaveNoViolations()
}

/**
 * Check accessibility and return detailed results
 *
 * @param container - The container element to test
 * @param config - Optional axe configuration
 * @returns Promise that resolves with detailed axe results
 *
 * @example
 * ```tsx
 * const { container } = render(<MyComponent />)
 * const results = await checkAccessibilityDetailed(container)
 * if (results.violations.length > 0) {
 *   console.log('Violations:', results.violations)
 * }
 * ```
 */
export async function checkAccessibilityDetailed(
  container: HTMLElement,
  config: typeof defaultAxeConfig = defaultAxeConfig
): Promise<AxeResults> {
  return await axe(container, config)
}

/**
 * Check accessibility with custom rules
 *
 * @param container - The container element to test
 * @param rules - Custom rules to enable/disable
 * @returns Promise that resolves when accessibility check is complete
 *
 * @example
 * ```tsx
 * await checkAccessibilityWithRules(container, {
 *   'color-contrast': { enabled: false }, // Disable color contrast check
 * })
 * ```
 */
export async function checkAccessibilityWithRules(
  container: HTMLElement,
  rules: Record<string, { enabled: boolean }>
): Promise<void> {
  const config = {
    ...defaultAxeConfig,
    rules: {
      ...defaultAxeConfig.rules,
      ...rules,
    },
  }
  await checkAccessibility(container, config)
}

/**
 * Check accessibility for a specific component pattern
 *
 * @param container - The container element to test
 * @param pattern - Component pattern to test (e.g., 'form', 'navigation', 'button')
 * @returns Promise that resolves when accessibility check is complete
 */
export async function checkAccessibilityPattern(
  container: HTMLElement,
  pattern: 'form' | 'navigation' | 'button' | 'link' | 'image' | 'table'
): Promise<void> {
  const patternRules: Record<string, Record<string, { enabled: boolean }>> = {
    // Use tag-based configuration instead of individual rules
    // This avoids invalid rule names
    form: {},
    navigation: {},
    button: {},
    link: {},
    image: {
      'image-alt': { enabled: true },
    },
    table: {
      'th-has-data-cells': { enabled: true },
      'td-headers-attr': { enabled: true },
    },
  }

  const rules = patternRules[pattern] || {}
  await checkAccessibilityWithRules(container, rules)
}

/**
 * Format accessibility violations for readable output
 *
 * @param violations - Array of accessibility violations
 * @returns Formatted string with violation details
 */
export function formatAccessibilityViolations(violations: AxeResults['violations']): string {
  return violations
    .map((violation) => {
      const nodes = violation.nodes.map((node) => {
        const target = node.target.join(', ')
        const failureSummary = node.failureSummary || 'No summary available'
        return `  - ${target}\n    ${failureSummary}`
      })

      return `${violation.id}: ${violation.description}\n${nodes.join('\n')}`
    })
    .join('\n\n')
}

/**
 * Assert that an element is keyboard accessible
 *
 * @param element - The element to test
 * @returns Promise that resolves when check is complete
 */
export async function assertKeyboardAccessible(element: HTMLElement): Promise<void> {
  // Check if element is focusable
  const isFocusable = element.tabIndex >= 0 || element.getAttribute('tabindex') !== null

  if (!isFocusable && element.tagName !== 'A' && element.tagName !== 'BUTTON' && element.tagName !== 'INPUT') {
    throw new Error(`Element ${element.tagName} is not keyboard accessible`)
  }

  // Check for keyboard event handlers
  const hasKeyboardHandlers =
    element.onkeydown !== null || element.onkeyup !== null || element.onkeypress !== null

  if (!hasKeyboardHandlers && element.getAttribute('role') === 'button') {
    // Buttons should have keyboard handlers or be native button elements
    if (element.tagName !== 'BUTTON') {
      throw new Error('Button role element should have keyboard handlers')
    }
  }
}

/**
 * Assert that an element has proper ARIA attributes
 *
 * @param element - The element to test
 * @param requiredAttributes - Array of required ARIA attribute names
 * @returns Promise that resolves when check is complete
 */
export async function assertAriaAttributes(
  element: HTMLElement,
  requiredAttributes: string[] = []
): Promise<void> {
  for (const attr of requiredAttributes) {
    if (!element.hasAttribute(attr) && !element.hasAttribute(`aria-${attr}`)) {
      throw new Error(`Element missing required ARIA attribute: ${attr}`)
    }
  }
}

/**
 * Assert that form inputs have associated labels
 *
 * @param input - The input element to test
 * @returns Promise that resolves when check is complete
 */
export async function assertInputHasLabel(input: HTMLElement): Promise<void> {
  const id = input.getAttribute('id')
  const ariaLabel = input.getAttribute('aria-label')
  const ariaLabelledBy = input.getAttribute('aria-labelledby')

  if (!id && !ariaLabel && !ariaLabelledBy) {
    // Check for implicit label (input inside label)
    const parentLabel = input.closest('label')
    if (!parentLabel) {
      throw new Error('Input element must have an associated label')
    }
  }

  if (id) {
    const label = document.querySelector(`label[for="${id}"]`)
    if (!label && !ariaLabel && !ariaLabelledBy) {
      throw new Error(`Input with id "${id}" must have an associated label`)
    }
  }
}

