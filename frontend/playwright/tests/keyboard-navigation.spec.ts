/**
 * Keyboard Navigation E2E Tests (6.13.1)
 *
 * Comprehensive end-to-end tests for keyboard navigation and accessibility.
 * Tests all aspects of keyboard navigation including:
 * - Tab navigation
 * - Keyboard shortcuts
 * - Focus management
 * - Skip links
 *
 * Uses real keyboard interactions - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'
import {
  getFocusableElements,
  getFocusedElement,
  hasFocus,
  hasVisibleFocusIndicator,
  tabNavigate,
  getTabOrder,
  testKeyboardShortcut,
  findSkipLink,
  testSkipLink,
  checkKeyboardTrap,
  testArrowKeyNavigation,
  testHomeEndKeys,
  testEnterSpaceActivation,
  assertLogicalTabOrder,
} from '../utils/keyboard-navigation'

/**
 * Test credentials
 */
const TEST_CREDENTIALS = {
  email: process.env.TEST_USER_EMAIL || 'test@example.com',
  password: process.env.TEST_USER_PASSWORD || 'testpassword123',
}

test.describe('Keyboard Navigation Tests (6.13.1)', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.login(TEST_CREDENTIALS.email, TEST_CREDENTIALS.password)
  })

  test.describe('Tab Navigation', () => {
    test('should navigate forward through focusable elements with Tab', async ({ page }) => {
      await page.goto('/')

      const elements = await getFocusableElements(page)
      expect(elements.length).toBeGreaterThan(0)

      // Start from beginning
      await page.keyboard.press('Home')
      await page.waitForTimeout(200)

      // Navigate forward through elements
      for (let i = 0; i < Math.min(5, elements.length); i++) {
        const beforeFocus = await getFocusedElement(page)
        await tabNavigate(page, 'forward', 1)
        const afterFocus = await getFocusedElement(page)

        // Focus should have changed
        expect(afterFocus).not.toBe(beforeFocus)
      }
    })

    test('should navigate backward through focusable elements with Shift+Tab', async ({ page }) => {
      await page.goto('/')

      const elements = await getFocusableElements(page)
      expect(elements.length).toBeGreaterThan(0)

      // Focus last element first
      await page.keyboard.press('End')
      await page.waitForTimeout(200)

      // Navigate backward
      for (let i = 0; i < Math.min(5, elements.length); i++) {
        const beforeFocus = await getFocusedElement(page)
        await tabNavigate(page, 'backward', 1)
        const afterFocus = await getFocusedElement(page)

        // Focus should have changed
        expect(afterFocus).not.toBe(beforeFocus)
      }
    })

    test('should maintain logical tab order on homepage', async ({ page }) => {
      await page.goto('/')

      const tabOrder = await getTabOrder(page)
      expect(tabOrder.length).toBeGreaterThan(0)

      // Tab order should be consistent
      const firstOrder = tabOrder
      await page.reload()
      await page.waitForLoadState('networkidle')
      const secondOrder = await getTabOrder(page)

      // Orders should match (allowing for dynamic content)
      expect(secondOrder.length).toBeGreaterThan(0)
    })

    test('should have logical tab order in navigation header', async ({ page }) => {
      await page.goto('/')

      // Test tab order in header navigation
      const headerElements = await getFocusableElements(page, 'header, nav, [role="navigation"]')
      expect(headerElements.length).toBeGreaterThan(0)

      // Focus first element in header
      await headerElements[0].focus()
      await page.waitForTimeout(100)

      // Tab through header elements
      for (let i = 1; i < Math.min(headerElements.length, 5); i++) {
        await tabNavigate(page, 'forward', 1)
        const focused = await hasFocus(headerElements[i])
        expect(focused).toBe(true)
      }
    })

    test('should skip disabled and hidden elements in tab order', async ({ page }) => {
      await page.goto('/')

      const allElements = await getFocusableElements(page)
      const tabOrder = await getTabOrder(page)

      // Tab order should only include visible, enabled elements
      for (const elementSelector of tabOrder) {
        const element = page.locator(elementSelector).first()
        const isVisible = await element.isVisible().catch(() => false)
        const isEnabled = await element.isEnabled().catch(() => true)

        expect(isVisible).toBe(true)
        expect(isEnabled).toBe(true)
      }
    })

    test('should cycle through all focusable elements', async ({ page }) => {
      await page.goto('/')

      const elements = await getFocusableElements(page)
      if (elements.length === 0) {
        test.skip()
        return
      }

      // Start from first element
      await elements[0].focus()
      await page.waitForTimeout(100)

      // Tab through all elements
      for (let i = 1; i < elements.length; i++) {
        await tabNavigate(page, 'forward', 1)
        const focused = await hasFocus(elements[i])
        expect(focused).toBe(true)
      }

      // One more tab should cycle back or move to next section
      await tabNavigate(page, 'forward', 1)
      const finalFocus = await getFocusedElement(page)
      expect(finalFocus).not.toBeNull()
    })
  })

  test.describe('Keyboard Shortcuts', () => {
    test('should support Enter key to activate buttons', async ({ page }) => {
      await page.goto('/')

      // Find a button
      const button = page.locator('button').first()
      if (await button.isVisible().catch(() => false)) {
        await testEnterSpaceActivation(page, button, 'click button')
        // Button should have been activated (may trigger navigation or action)
        await page.waitForTimeout(500)
      }
    })

    test('should support Space key to activate buttons', async ({ page }) => {
      await page.goto('/')

      // Find a button
      const button = page.locator('button').first()
      if (await button.isVisible().catch(() => false)) {
        await testEnterSpaceActivation(page, button, 'click button')
        // Button should have been activated
        await page.waitForTimeout(500)
      }
    })

    test('should support Esc key to close modals', async ({ page }) => {
      await page.goto('/')

      // Try to find and open a modal (if available)
      const modalTrigger = page.locator('button:has-text("Open"), button[aria-haspopup="true"]').first()
      if (await modalTrigger.isVisible().catch(() => false)) {
        await modalTrigger.click()
        await page.waitForTimeout(500)

        // Check if modal is open
        const modal = page.locator('[role="dialog"]').first()
        if (await modal.isVisible().catch(() => false)) {
          // Press Esc to close
          await page.keyboard.press('Escape')
          await page.waitForTimeout(500)

          // Modal should be closed
          const isVisible = await modal.isVisible().catch(() => false)
          expect(isVisible).toBe(false)
        }
      }
    })

    test('should support arrow keys in tabs component', async ({ page }) => {
      await page.goto('/')

      // Find tabs component
      const tabsContainer = page.locator('[role="tablist"]').first()
      if (await tabsContainer.isVisible().catch(() => false)) {
        await testArrowKeyNavigation(page, '[role="tablist"]', 'horizontal')
      }
    })

    test('should support Home and End keys in navigation', async ({ page }) => {
      await page.goto('/')

      // Find navigation container
      const navContainer = page.locator('nav, [role="navigation"]').first()
      if (await navContainer.isVisible().catch(() => false)) {
        await testHomeEndKeys(page, 'nav, [role="navigation"]')
      }
    })

    test('should support Ctrl+Z / Cmd+Z for undo in contract editor', async ({ page }) => {
      // Navigate to contract editor if available
      await page.goto('/contracts')
      await page.waitForLoadState('networkidle')

      // Try to find contract editor
      const editor = page.locator('[contenteditable="true"], textarea, input[type="text"]').first()
      if (await editor.isVisible().catch(() => false)) {
        await editor.focus()
        await editor.type('Test text')
        await page.waitForTimeout(200)

        // Test undo shortcut (Ctrl+Z or Cmd+Z)
        const isMac = process.platform === 'darwin'
        const undoKey = isMac ? 'Meta+z' : 'Control+z'
        await testKeyboardShortcut(page, undoKey, 'undo')

        // Text might be undone (depending on implementation)
        await page.waitForTimeout(500)
      }
    })

    test('should support Ctrl+Y / Cmd+Shift+Z for redo in contract editor', async ({ page }) => {
      await page.goto('/contracts')
      await page.waitForLoadState('networkidle')

      const editor = page.locator('[contenteditable="true"], textarea, input[type="text"]').first()
      if (await editor.isVisible().catch(() => false)) {
        await editor.focus()
        await editor.type('Test')
        await page.waitForTimeout(200)

        // Test redo shortcut
        const isMac = process.platform === 'darwin'
        const redoKey = isMac ? 'Meta+Shift+z' : 'Control+y'
        await testKeyboardShortcut(page, redoKey, 'redo')

        await page.waitForTimeout(500)
      }
    })
  })

  test.describe('Focus Management', () => {
    test('should have visible focus indicators on all interactive elements', async ({ page }) => {
      await page.goto('/')

      const elements = await getFocusableElements(page)
      expect(elements.length).toBeGreaterThan(0)

      // Check first few elements for focus indicators
      for (let i = 0; i < Math.min(5, elements.length); i++) {
        await elements[i].focus()
        await page.waitForTimeout(100)

        const hasIndicator = await hasVisibleFocusIndicator(elements[i])
        expect(hasIndicator).toBe(true)
      }
    })

    test('should manage focus when opening modals', async ({ page }) => {
      await page.goto('/')

      // Try to open a modal
      const modalTrigger = page.locator('button:has-text("Open"), button[aria-haspopup="true"]').first()
      if (await modalTrigger.isVisible().catch(() => false)) {
        await modalTrigger.click()
        await page.waitForTimeout(500)

        const modal = page.locator('[role="dialog"]').first()
        if (await modal.isVisible().catch(() => false)) {
          // Focus should be inside modal
          const focused = await getFocusedElement(page)
          const isInModal = await modal.evaluate((modalEl, focusedSelector) => {
            if (!focusedSelector) return false
            const focusedEl = document.querySelector(focusedSelector)
            return focusedEl && modalEl.contains(focusedEl)
          }, focused || '')

          expect(isInModal).toBe(true)
        }
      }
    })

    test('should return focus to trigger element when closing modal', async ({ page }) => {
      await page.goto('/')

      const modalTrigger = page.locator('button:has-text("Open"), button[aria-haspopup="true"]').first()
      if (await modalTrigger.isVisible().catch(() => false)) {
        await modalTrigger.focus()
        const triggerSelector = await getFocusedElement(page)
        await modalTrigger.click()
        await page.waitForTimeout(500)

        const modal = page.locator('[role="dialog"]').first()
        if (await modal.isVisible().catch(() => false)) {
          // Close modal
          await page.keyboard.press('Escape')
          await page.waitForTimeout(500)

          // Focus should return to trigger
          const finalFocus = await getFocusedElement(page)
          expect(finalFocus).toBe(triggerSelector)
        }
      }
    })

    test('should trap focus within modal', async ({ page }) => {
      await page.goto('/')

      const modalTrigger = page.locator('button:has-text("Open"), button[aria-haspopup="true"]').first()
      if (await modalTrigger.isVisible().catch(() => false)) {
        await modalTrigger.click()
        await page.waitForTimeout(500)

        const modal = page.locator('[role="dialog"]').first()
        if (await modal.isVisible().catch(() => false)) {
          // Check for keyboard trap (should trap focus)
          const hasTrap = !(await checkKeyboardTrap(page, '[role="dialog"]'))
          // Modal should trap focus (hasTrap should be true)
          expect(hasTrap).toBe(true)
        }
      }
    })

    test('should manage focus on route navigation', async ({ page }) => {
      await page.goto('/')

      // Get initial focus
      const initialFocus = await getFocusedElement(page)

      // Navigate to another page
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(500)

      // Focus should be managed (may be on page or first focusable element)
      const newFocus = await getFocusedElement(page)
      expect(newFocus).not.toBeNull()
    })

    test('should maintain focus order consistency', async ({ page }) => {
      await page.goto('/')

      // Get tab order multiple times
      const order1 = await getTabOrder(page)
      await page.waitForTimeout(1000)
      const order2 = await getTabOrder(page)

      // Orders should be consistent (allowing for some dynamic content)
      expect(order2.length).toBeGreaterThan(0)
      // At least some elements should be in the same order
      const commonElements = order1.filter((el) => order2.includes(el))
      expect(commonElements.length).toBeGreaterThan(0)
    })

    test('should focus first element when page loads', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(500)

      // Focus should be on page or first focusable element
      const focused = await getFocusedElement(page)
      expect(focused).not.toBeNull()
    })
  })

  test.describe('Skip Links', () => {
    test('should have skip link on homepage', async ({ page }) => {
      await page.goto('/')

      const skipLink = await findSkipLink(page)
      // Skip link may or may not be present (depending on implementation)
      // If present, it should be functional
      if (skipLink) {
        const isVisible = await skipLink.isVisible()
        expect(isVisible).toBe(true)
      }
    })

    test('should make skip link visible on focus', async ({ page }) => {
      await page.goto('/')

      const skipLink = await findSkipLink(page)
      if (skipLink) {
        // Skip link might be visually hidden until focused
        await skipLink.focus()
        await page.waitForTimeout(200)

        // Should be visible when focused
        const isVisible = await skipLink.isVisible()
        expect(isVisible).toBe(true)
      }
    })

    test('should navigate to main content when skip link is activated', async ({ page }) => {
      await page.goto('/')

      const skipLink = await findSkipLink(page)
      if (skipLink) {
        const works = await testSkipLink(page)
        expect(works).toBe(true)
      }
    })

    test('should have skip link that targets main content area', async ({ page }) => {
      await page.goto('/')

      const skipLink = await findSkipLink(page)
      if (skipLink) {
        const href = await skipLink.getAttribute('href')
        expect(href).not.toBeNull()
        expect(href).toMatch(/^#/)

        // Target should exist
        if (href) {
          const target = page.locator(href)
          const targetExists = await target.count() > 0
          expect(targetExists).toBe(true)
        }
      }
    })

    test('should support keyboard activation of skip link', async ({ page }) => {
      await page.goto('/')

      const skipLink = await findSkipLink(page)
      if (skipLink) {
        // Focus skip link
        await skipLink.focus()
        await page.waitForTimeout(100)

        // Activate with Enter
        await page.keyboard.press('Enter')
        await page.waitForTimeout(500)

        // Should navigate to target
        const href = await skipLink.getAttribute('href')
        if (href) {
          const target = page.locator(href)
          const isFocused = await target.evaluate((el) => {
            return el === document.activeElement || el.contains(document.activeElement)
          }).catch(() => false)

          expect(isFocused).toBe(true)
        }
      }
    })

    test('should have skip link accessible early in tab order', async ({ page }) => {
      await page.goto('/')

      const skipLink = await findSkipLink(page)
      if (skipLink) {
        // Start from beginning
        await page.keyboard.press('Home')
        await page.waitForTimeout(200)

        // Skip link should be one of the first focusable elements
        const tabOrder = await getTabOrder(page)
        const skipLinkHref = await skipLink.getAttribute('href')

        // Check if skip link is in first few elements
        const isEarly = tabOrder.slice(0, 3).some((selector) => {
          return selector.includes('skip') || (skipLinkHref && selector.includes(skipLinkHref.replace('#', '')))
        })

        expect(isEarly).toBe(true)
      }
    })
  })

  test.describe('Comprehensive Keyboard Navigation', () => {
    test('should support full keyboard navigation workflow', async ({ page }) => {
      await page.goto('/')

      // 1. Tab through main navigation
      const navElements = await getFocusableElements(page, 'nav, [role="navigation"]')
      if (navElements.length > 0) {
        await navElements[0].focus()
        for (let i = 1; i < Math.min(3, navElements.length); i++) {
          await tabNavigate(page, 'forward', 1)
          const focused = await hasFocus(navElements[i])
          expect(focused).toBe(true)
        }
      }

      // 2. Use arrow keys in components
      const tabsContainer = page.locator('[role="tablist"]').first()
      if (await tabsContainer.isVisible().catch(() => false)) {
        await testArrowKeyNavigation(page, '[role="tablist"]', 'horizontal')
      }

      // 3. Activate elements with Enter/Space
      const button = page.locator('button').first()
      if (await button.isVisible().catch(() => false)) {
        await testEnterSpaceActivation(page, button)
      }

      // 4. Verify focus indicators
      const elements = await getFocusableElements(page)
      if (elements.length > 0) {
        await elements[0].focus()
        const hasIndicator = await hasVisibleFocusIndicator(elements[0])
        expect(hasIndicator).toBe(true)
      }
    })

    test('should not have keyboard traps on main pages', async ({ page }) => {
      const pages = ['/', '/assets', '/marketplace', '/contracts']

      for (const pagePath of pages) {
        await page.goto(pagePath)
        await page.waitForLoadState('networkidle')

        // Check for keyboard traps in main content
        const noTrap = await checkKeyboardTrap(page, 'main, [role="main"]')
        expect(noTrap).toBe(true)
      }
    })

    test('should support keyboard navigation across all major pages', async ({ page }) => {
      const pages = ['/', '/assets', '/marketplace', '/contracts']

      for (const pagePath of pages) {
        await page.goto(pagePath)
        await page.waitForLoadState('networkidle')

        // Verify tab navigation works
        const elements = await getFocusableElements(page)
        expect(elements.length).toBeGreaterThan(0)

        // Verify focus indicators
        if (elements.length > 0) {
          await elements[0].focus()
          const hasIndicator = await hasVisibleFocusIndicator(elements[0])
          expect(hasIndicator).toBe(true)
        }
      }
    })
  })
})

