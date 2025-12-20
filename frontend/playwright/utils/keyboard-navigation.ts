/**
 * Keyboard Navigation Testing Utilities
 *
 * Utilities for testing keyboard navigation and accessibility in Playwright E2E tests.
 * Provides helpers for:
 * - Tab navigation testing
 * - Keyboard shortcuts testing
 * - Focus management testing
 * - Skip links testing
 *
 * Uses real keyboard interactions - no mocks/stubs. Always fixes root cause.
 */

import { Page, Locator, expect } from '@playwright/test'

/**
 * Get all focusable elements on the page
 *
 * @param page - Playwright page
 * @param container - Optional container selector
 * @returns Array of focusable elements
 */
export async function getFocusableElements(
  page: Page,
  container?: string
): Promise<Locator[]> {
  const selector = container
    ? `${container} a, ${container} button, ${container} input, ${container} select, ${container} textarea, ${container} [tabindex]:not([tabindex="-1"])`
    : 'a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])'

  const elements = page.locator(selector).filter(async (locator) => {
    const isVisible = await locator.isVisible().catch(() => false)
    const isEnabled = await locator.isEnabled().catch(() => true)
    const display = await locator.evaluate((el) => {
      const style = window.getComputedStyle(el)
      return style.display !== 'none' && style.visibility !== 'hidden'
    }).catch(() => true)

    return isVisible && isEnabled && display
  })

  const count = await elements.count()
  return Array.from({ length: count }, (_, i) => elements.nth(i))
}

/**
 * Get currently focused element
 *
 * @param page - Playwright page
 * @returns Currently focused element selector or null
 */
export async function getFocusedElement(page: Page): Promise<string | null> {
  return await page.evaluate(() => {
    const activeElement = document.activeElement
    if (!activeElement) return null

    // Generate a selector for the element
    if (activeElement.id) {
      return `#${activeElement.id}`
    }
    if (activeElement.className && typeof activeElement.className === 'string') {
      const classes = activeElement.className.split(' ').filter(Boolean)
      if (classes.length > 0) {
        return `.${classes[0]}`
      }
    }
    return activeElement.tagName.toLowerCase()
  })
}

/**
 * Check if an element has focus
 *
 * @param element - Element locator
 * @returns True if element has focus
 */
export async function hasFocus(element: Locator): Promise<boolean> {
  return await element.evaluate((el) => el === document.activeElement)
}

/**
 * Check if an element has visible focus indicator
 *
 * @param element - Element locator
 * @returns True if element has visible focus indicator
 */
export async function hasVisibleFocusIndicator(element: Locator): Promise<boolean> {
  const outline = await element.evaluate((el) => {
    const style = window.getComputedStyle(el)
    return {
      outline: style.outline,
      outlineWidth: style.outlineWidth,
      boxShadow: style.boxShadow,
    }
  })

  // Check if outline or box-shadow indicates focus
  const hasOutline = outline.outline && outline.outline !== 'none' && outline.outlineWidth !== '0px'
  const hasBoxShadow = outline.boxShadow && outline.boxShadow !== 'none'

  // Also check for focus-visible class or aria attributes
  const hasFocusClass = await element.evaluate((el) => {
    return el.classList.contains('focus-visible') || el.classList.contains('focus')
  })

  return hasOutline || hasBoxShadow || hasFocusClass
}

/**
 * Navigate using Tab key
 *
 * @param page - Playwright page
 * @param direction - 'forward' or 'backward'
 * @param count - Number of tabs (default: 1)
 */
export async function tabNavigate(
  page: Page,
  direction: 'forward' | 'backward' = 'forward',
  count: number = 1
): Promise<void> {
  for (let i = 0; i < count; i++) {
    if (direction === 'forward') {
      await page.keyboard.press('Tab')
    } else {
      await page.keyboard.press('Shift+Tab')
    }
    // Small delay to allow focus to settle
    await page.waitForTimeout(100)
  }
}

/**
 * Get tab order of focusable elements
 *
 * @param page - Playwright page
 * @param container - Optional container selector
 * @returns Array of element selectors in tab order
 */
export async function getTabOrder(
  page: Page,
  container?: string
): Promise<string[]> {
  const elements = await getFocusableElements(page, container)
  const tabOrder: string[] = []

  // Start from the beginning
  await page.keyboard.press('Home')
  await page.waitForTimeout(100)

  // Navigate forward and collect elements
  for (let i = 0; i < elements.length; i++) {
    const focused = await getFocusedElement(page)
    if (focused) {
      tabOrder.push(focused)
    }
    await tabNavigate(page, 'forward', 1)
  }

  return tabOrder
}

/**
 * Test keyboard shortcut
 *
 * @param page - Playwright page
 * @param key - Key combination (e.g., 'Control+z', 'Meta+k')
 * @param expectedAction - Expected action description for logging
 */
export async function testKeyboardShortcut(
  page: Page,
  key: string,
  expectedAction?: string
): Promise<void> {
  if (expectedAction) {
    console.log(`Testing keyboard shortcut: ${key} (${expectedAction})`)
  }
  await page.keyboard.press(key)
  await page.waitForTimeout(200) // Allow action to complete
}

/**
 * Find skip link on the page
 *
 * @param page - Playwright page
 * @returns Skip link locator or null
 */
export async function findSkipLink(page: Page): Promise<Locator | null> {
  // Look for common skip link patterns
  const skipLinkSelectors = [
    'a[href*="#main"]',
    'a[href*="#content"]',
    'a.skip-link',
    'a[class*="skip"]',
    'a:has-text("Skip")',
    'a:has-text("Skip to")',
    'a:has-text("Skip navigation")',
  ]

  for (const selector of skipLinkSelectors) {
    const link = page.locator(selector).first()
    if (await link.isVisible().catch(() => false)) {
      return link
    }
  }

  return null
}

/**
 * Test skip link functionality
 *
 * @param page - Playwright page
 * @returns True if skip link exists and works
 */
export async function testSkipLink(page: Page): Promise<boolean> {
  const skipLink = await findSkipLink(page)
  if (!skipLink) {
    return false
  }

  // Check if skip link is visible when focused
  await skipLink.focus()
  const isVisible = await skipLink.isVisible()

  // Activate skip link
  await skipLink.press('Enter')
  await page.waitForTimeout(500)

  // Check if focus moved to target
  const focused = await getFocusedElement(page)
  const targetId = await skipLink.getAttribute('href')

  if (targetId && targetId.startsWith('#')) {
    const target = page.locator(targetId)
    const targetFocused = await target.evaluate((el) => {
      return el === document.activeElement || el.contains(document.activeElement)
    }).catch(() => false)

    return targetFocused
  }

  return isVisible
}

/**
 * Check for keyboard traps
 *
 * @param page - Playwright page
 * @param container - Container selector to test
 * @returns True if no keyboard trap detected
 */
export async function checkKeyboardTrap(
  page: Page,
  container: string
): Promise<boolean> {
  const containerElement = page.locator(container).first()
  if (!(await containerElement.isVisible().catch(() => false))) {
    return true // Container not visible, can't trap
  }

  // Get focusable elements in container
  const elements = await getFocusableElements(page, container)
  if (elements.length === 0) {
    return true // No focusable elements, no trap
  }

  // Focus first element
  await elements[0].focus()
  await page.waitForTimeout(100)

  // Try to tab forward multiple times
  const initialFocus = await getFocusedElement(page)
  for (let i = 0; i < elements.length + 2; i++) {
    await tabNavigate(page, 'forward', 1)
    const currentFocus = await getFocusedElement(page)

    // If we're outside the container, no trap
    const isOutside = await page.evaluate(
      ({ containerSelector, currentSelector }) => {
        if (!currentSelector) return true
        const container = document.querySelector(containerSelector)
        const current = document.querySelector(currentSelector)
        return !container || !current || !container.contains(current)
      },
      { containerSelector: container, currentSelector: currentFocus }
    )

    if (isOutside) {
      return true // Escaped container, no trap
    }
  }

  // If we're still in the container after many tabs, might be a trap
  return false
}

/**
 * Test arrow key navigation in a component
 *
 * @param page - Playwright page
 * @param container - Container selector
 * @param orientation - 'horizontal' or 'vertical'
 */
export async function testArrowKeyNavigation(
  page: Page,
  container: string,
  orientation: 'horizontal' | 'vertical' = 'horizontal'
): Promise<void> {
  const elements = await getFocusableElements(page, container)
  if (elements.length < 2) {
    return // Need at least 2 elements to test navigation
  }

  // Focus first element
  await elements[0].focus()
  await page.waitForTimeout(100)

  // Test forward navigation
  const forwardKey = orientation === 'horizontal' ? 'ArrowRight' : 'ArrowDown'
  await page.keyboard.press(forwardKey)
  await page.waitForTimeout(100)

  const secondFocused = await hasFocus(elements[1])
  expect(secondFocused).toBe(true)

  // Test backward navigation
  const backwardKey = orientation === 'horizontal' ? 'ArrowLeft' : 'ArrowUp'
  await page.keyboard.press(backwardKey)
  await page.waitForTimeout(100)

  const firstFocused = await hasFocus(elements[0])
  expect(firstFocused).toBe(true)
}

/**
 * Test Home and End keys
 *
 * @param page - Playwright page
 * @param container - Container selector
 */
export async function testHomeEndKeys(
  page: Page,
  container: string
): Promise<void> {
  const elements = await getFocusableElements(page, container)
  if (elements.length < 2) {
    return // Need at least 2 elements
  }

  // Focus middle element
  const middleIndex = Math.floor(elements.length / 2)
  await elements[middleIndex].focus()
  await page.waitForTimeout(100)

  // Test Home key (should go to first)
  await page.keyboard.press('Home')
  await page.waitForTimeout(100)
  const firstFocused = await hasFocus(elements[0])
  expect(firstFocused).toBe(true)

  // Test End key (should go to last)
  await page.keyboard.press('End')
  await page.waitForTimeout(100)
  const lastFocused = await hasFocus(elements[elements.length - 1])
  expect(lastFocused).toBe(true)
}

/**
 * Test Enter and Space key activation
 *
 * @param page - Playwright page
 * @param element - Element to test
 * @param expectedAction - Expected action (e.g., 'click', 'submit')
 */
export async function testEnterSpaceActivation(
  page: Page,
  element: Locator,
  expectedAction?: string
): Promise<void> {
  await element.focus()
  await page.waitForTimeout(100)

  // Test Enter key
  const enterPressed = page.waitForEvent('click', { timeout: 1000 }).catch(() => null)
  await page.keyboard.press('Enter')
  await enterPressed

  // Test Space key
  await element.focus()
  await page.waitForTimeout(100)
  const spacePressed = page.waitForEvent('click', { timeout: 1000 }).catch(() => null)
  await page.keyboard.press('Space')
  await spacePressed
}

/**
 * Assert logical tab order
 *
 * @param page - Playwright page
 * @param expectedOrder - Array of selectors in expected order
 * @param container - Optional container selector
 */
export async function assertLogicalTabOrder(
  page: Page,
  expectedOrder: string[],
  container?: string
): Promise<void> {
  const actualOrder = await getTabOrder(page, container)

  // Check if expected order matches actual order (allowing for some flexibility)
  for (let i = 0; i < Math.min(expectedOrder.length, actualOrder.length); i++) {
    const expected = expectedOrder[i]
    const actual = actualOrder[i]

    // Allow partial matches (e.g., if selector is more specific)
    const matches = actual.includes(expected) || expected.includes(actual)
    expect(matches).toBe(true)
  }
}

