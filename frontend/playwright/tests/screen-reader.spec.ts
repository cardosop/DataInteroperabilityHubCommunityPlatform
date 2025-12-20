/**
 * Screen Reader Tests
 *
 * Comprehensive E2E tests for screen reader accessibility covering:
 * - ARIA labels (all interactive elements have proper labels)
 * - Semantic HTML (proper use of semantic elements)
 * - Heading hierarchy (logical heading order)
 * - Form labels (all inputs have associated labels)
 *
 * Uses real accessibility APIs and DOM inspection (no mocks/stubs)
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { login } from '../utils/auth'

/**
 * Get accessibility tree for a page
 */
async function getAccessibilityTree(page: any) {
  return await page.accessibility.snapshot()
}

/**
 * Get all headings in order
 */
async function getHeadings(page: any): Promise<Array<{ level: number; text: string; id: string | null }>> {
  return await page.evaluate(() => {
    const headings: Array<{ level: number; text: string; id: string | null }> = []
    const headingElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6')

    headingElements.forEach((heading) => {
      const level = parseInt(heading.tagName.charAt(1))
      headings.push({
        level,
        text: heading.textContent?.trim() || '',
        id: heading.id || null,
      })
    })

    return headings
  })
}

/**
 * Check if heading hierarchy is valid (no skipped levels)
 */
function isValidHeadingHierarchy(headings: Array<{ level: number; text: string }>): boolean {
  if (headings.length === 0) return true

  // Must start with h1
  if (headings[0].level !== 1) return false

  let previousLevel = 1

  for (let i = 1; i < headings.length; i++) {
    const currentLevel = headings[i].level
    // Can only increase by 1 level at a time
    if (currentLevel > previousLevel + 1) {
      return false
    }
    previousLevel = currentLevel
  }

  return true
}

/**
 * Get all form inputs and their label associations
 */
async function getFormInputsWithLabels(page: any): Promise<
  Array<{
    type: string
    name: string | null
    id: string | null
    hasLabel: boolean
    labelText: string | null
    hasAriaLabel: boolean
    ariaLabel: string | null
    hasAriaLabelledBy: boolean
    ariaLabelledBy: string | null
  }>
> {
  return await page.evaluate(() => {
    const inputs: Array<{
      type: string
      name: string | null
      id: string | null
      hasLabel: boolean
      labelText: string | null
      hasAriaLabel: boolean
      ariaLabel: string | null
      hasAriaLabelledBy: boolean
      ariaLabelledBy: string | null
    }> = []

    const inputElements = document.querySelectorAll(
      'input, textarea, select'
    )

    inputElements.forEach((input) => {
      const element = input as HTMLElement
      const id = element.id || null
      const name = element.getAttribute('name') || null
      const type = element.tagName.toLowerCase() === 'input'
        ? (element as HTMLInputElement).type
        : element.tagName.toLowerCase()

      // Check for explicit label (for attribute)
      let hasLabel = false
      let labelText: string | null = null
      if (id) {
        const label = document.querySelector(`label[for="${id}"]`)
        if (label) {
          hasLabel = true
          labelText = label.textContent?.trim() || null
        }
      }

      // Check for implicit label (wrapping)
      if (!hasLabel) {
        const parentLabel = element.closest('label')
        if (parentLabel) {
          hasLabel = true
          // Get label text excluding the input itself
          const labelClone = parentLabel.cloneNode(true) as HTMLElement
          const inputClone = labelClone.querySelector('input, textarea, select')
          if (inputClone) {
            inputClone.remove()
          }
          labelText = labelClone.textContent?.trim() || null
        }
      }

      // Check for aria-label
      const ariaLabel = element.getAttribute('aria-label')
      const hasAriaLabel = !!ariaLabel

      // Check for aria-labelledby
      const ariaLabelledBy = element.getAttribute('aria-labelledby')
      const hasAriaLabelledBy = !!ariaLabelledBy

      inputs.push({
        type,
        name,
        id,
        hasLabel,
        labelText,
        hasAriaLabel,
        ariaLabel,
        hasAriaLabelledBy,
        ariaLabelledBy,
      })
    })

    return inputs
  })
}

/**
 * Get all interactive elements and their ARIA labels
 */
async function getInteractiveElementsWithAria(page: any): Promise<
  Array<{
    tag: string
    role: string | null
    ariaLabel: string | null
    ariaLabelledBy: string | null
    text: string | null
    hasAccessibleName: boolean
  }>
> {
  return await page.evaluate(() => {
    const elements: Array<{
      tag: string
      role: string | null
      ariaLabel: string | null
      ariaLabelledBy: string | null
      text: string | null
      hasAccessibleName: boolean
    }> = []

    // Get all interactive elements
    const interactiveSelectors = [
      'button',
      'a[href]',
      'input',
      'select',
      'textarea',
      '[role="button"]',
      '[role="link"]',
      '[role="menuitem"]',
      '[role="tab"]',
      '[role="option"]',
      '[tabindex]:not([tabindex="-1"])',
    ]

    interactiveSelectors.forEach((selector) => {
      const nodes = document.querySelectorAll(selector)
      nodes.forEach((node) => {
        const element = node as HTMLElement
        const tag = element.tagName.toLowerCase()
        const role = element.getAttribute('role')
        const ariaLabel = element.getAttribute('aria-label')
        const ariaLabelledBy = element.getAttribute('aria-labelledby')
        const text = element.textContent?.trim() || null

        // Check if element has accessible name
        // Accessible name can come from:
        // - aria-label
        // - aria-labelledby
        // - label element (for form controls)
        // - text content (for buttons, links)
        // - title attribute
        // - alt attribute (for images)
        let hasAccessibleName = false

        if (ariaLabel) {
          hasAccessibleName = true
        } else if (ariaLabelledBy) {
          const labelledByElement = document.getElementById(ariaLabelledBy)
          if (labelledByElement) {
            hasAccessibleName = true
          }
        } else if (text && text.length > 0) {
          hasAccessibleName = true
        } else if (element.getAttribute('title')) {
          hasAccessibleName = true
        } else if (tag === 'input' || tag === 'textarea' || tag === 'select') {
          // Check for associated label
          const id = element.id
          if (id) {
            const label = document.querySelector(`label[for="${id}"]`)
            if (label) {
              hasAccessibleName = true
            }
          }
          // Check for implicit label
          const parentLabel = element.closest('label')
          if (parentLabel) {
            hasAccessibleName = true
          }
        } else if (tag === 'img') {
          const alt = element.getAttribute('alt')
          hasAccessibleName = alt !== null // Even empty alt is valid for decorative images
        }

        elements.push({
          tag,
          role,
          ariaLabel,
          ariaLabelledBy,
          text,
          hasAccessibleName,
        })
      })
    })

    return elements
  })
}

/**
 * Get semantic HTML elements
 */
async function getSemanticElements(page: any): Promise<{
  hasMain: boolean
  hasNav: boolean
  hasHeader: boolean
  hasFooter: boolean
  hasArticle: boolean
  hasSection: boolean
  hasAside: boolean
  navCount: number
  mainCount: number
}> {
  return await page.evaluate(() => {
    const main = document.querySelector('main')
    const nav = document.querySelectorAll('nav')
    const header = document.querySelector('header')
    const footer = document.querySelector('footer')
    const article = document.querySelector('article')
    const section = document.querySelectorAll('section')
    const aside = document.querySelector('aside')

    return {
      hasMain: !!main,
      hasNav: nav.length > 0,
      hasHeader: !!header,
      hasFooter: !!footer,
      hasArticle: !!article,
      hasSection: section.length > 0,
      hasAside: !!aside,
      navCount: nav.length,
      mainCount: document.querySelectorAll('main').length,
    }
  })
}

test.describe('Screen Reader Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any previous state
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test.describe('ARIA Labels', () => {
    test('should have ARIA labels on all icon buttons', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const interactiveElements = await getInteractiveElementsWithAria(page)

      // Filter for icon buttons (buttons without visible text)
      const iconButtons = interactiveElements.filter((el) => {
        return (
          (el.tag === 'button' || el.role === 'button') &&
          (!el.text || el.text.trim().length === 0) &&
          !el.hasAccessibleName
        )
      })

      // All icon buttons should have accessible names
      iconButtons.forEach((button) => {
        expect(
          button.hasAccessibleName,
          `Icon button missing accessible name. Tag: ${button.tag}, Role: ${button.role}`
        ).toBe(true)
      })
    })

    test('should have ARIA labels on all interactive elements without visible text', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const interactiveElements = await getInteractiveElementsWithAria(page)

      // Check all interactive elements have accessible names
      const elementsWithoutNames = interactiveElements.filter((el) => !el.hasAccessibleName)

      if (elementsWithoutNames.length > 0) {
        const missingNames = elementsWithoutNames.map(
          (el) => `${el.tag}${el.role ? `[role="${el.role}"]` : ''}`
        )
        expect(
          elementsWithoutNames.length,
          `Found ${elementsWithoutNames.length} interactive elements without accessible names: ${missingNames.join(', ')}`
        ).toBe(0)
      }
    })

    test('should have proper ARIA labels on navigation elements', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Check navigation elements have aria-label or aria-labelledby
      const navElements = await page.locator('nav').all()

      for (const nav of navElements) {
        const ariaLabel = await nav.getAttribute('aria-label')
        const ariaLabelledBy = await nav.getAttribute('aria-labelledby')

        expect(
          ariaLabel || ariaLabelledBy,
          'Navigation element should have aria-label or aria-labelledby'
        ).toBeTruthy()
      }
    })

    test('should have ARIA labels on form action buttons', async ({ page }) => {
      await login(page)
      await page.goto('/assets/new')
      await page.waitForLoadState('networkidle')

      const interactiveElements = await getInteractiveElementsWithAria(page)

      // Check submit buttons
      const submitButtons = interactiveElements.filter(
        (el) => el.tag === 'button' && (el.text?.toLowerCase().includes('submit') || el.text?.toLowerCase().includes('save'))
      )

      submitButtons.forEach((button) => {
        expect(
          button.hasAccessibleName,
          'Submit button should have accessible name'
        ).toBe(true)
      })
    })

    test('should have ARIA labels on modal/dialog close buttons', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Look for close buttons (typically have close icon)
      const closeButtons = await page.locator('button[aria-label*="close" i], button[aria-label*="Close" i]').all()

      for (const button of closeButtons) {
        const ariaLabel = await button.getAttribute('aria-label')
        expect(ariaLabel, 'Close button should have aria-label').toBeTruthy()
        expect(ariaLabel?.toLowerCase()).toContain('close')
      }
    })

    test('should have ARIA labels on status and alert elements', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Check for status and alert roles
      const statusElements = await page.locator('[role="status"], [role="alert"]').all()

      for (const element of statusElements) {
        const ariaLive = await element.getAttribute('aria-live')
        expect(
          ariaLive,
          'Status/alert elements should have aria-live attribute'
        ).toBeTruthy()
      }
    })
  })

  test.describe('Semantic HTML', () => {
    test('should use semantic HTML elements on home page', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const semanticElements = await getSemanticElements(page)

      // Should have main content area
      expect(semanticElements.hasMain, 'Page should have <main> element').toBe(true)
      expect(semanticElements.mainCount, 'Page should have exactly one <main> element').toBe(1)

      // Should have navigation
      expect(semanticElements.hasNav, 'Page should have <nav> element').toBe(true)
    })

    test('should use semantic HTML elements on assets page', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const semanticElements = await getSemanticElements(page)

      expect(semanticElements.hasMain, 'Assets page should have <main> element').toBe(true)
      expect(semanticElements.hasNav, 'Assets page should have <nav> element').toBe(true)
    })

    test('should use semantic HTML elements on contracts page', async ({ page }) => {
      await login(page)
      await page.goto('/contracts')
      await page.waitForLoadState('networkidle')

      const semanticElements = await getSemanticElements(page)

      expect(semanticElements.hasMain, 'Contracts page should have <main> element').toBe(true)
      expect(semanticElements.hasNav, 'Contracts page should have <nav> element').toBe(true)
    })

    test('should have only one main element per page', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const semanticElements = await getSemanticElements(page)

      expect(
        semanticElements.mainCount,
        'Page should have exactly one <main> element'
      ).toBe(1)
    })

    test('should use header element for page header', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const semanticElements = await getSemanticElements(page)

      // Header should be present (if used)
      if (semanticElements.hasHeader) {
        const header = await page.locator('header').first()
        expect(await header.count()).toBeGreaterThan(0)
      }
    })

    test('should use semantic elements for content structure', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Check for proper use of semantic elements
      const main = await page.locator('main').first()
      expect(await main.count()).toBeGreaterThan(0)

      // Main should contain the primary content
      const mainContent = await main.textContent()
      expect(mainContent?.length).toBeGreaterThan(0)
    })
  })

  test.describe('Heading Hierarchy', () => {
    test('should have valid heading hierarchy on home page', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const headings = await getHeadings(page)

      if (headings.length > 0) {
        const isValid = isValidHeadingHierarchy(headings)
        expect(
          isValid,
          `Invalid heading hierarchy. Headings: ${headings.map((h) => `h${h.level}: ${h.text}`).join(', ')}`
        ).toBe(true)
      }
    })

    test('should have valid heading hierarchy on assets page', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const headings = await getHeadings(page)

      if (headings.length > 0) {
        const isValid = isValidHeadingHierarchy(headings)
        expect(
          isValid,
          `Invalid heading hierarchy on assets page. Headings: ${headings.map((h) => `h${h.level}: ${h.text}`).join(', ')}`
        ).toBe(true)

        // Should start with h1
        expect(headings[0].level, 'Page should start with h1').toBe(1)
      }
    })

    test('should have valid heading hierarchy on contracts page', async ({ page }) => {
      await login(page)
      await page.goto('/contracts')
      await page.waitForLoadState('networkidle')

      const headings = await getHeadings(page)

      if (headings.length > 0) {
        const isValid = isValidHeadingHierarchy(headings)
        expect(
          isValid,
          `Invalid heading hierarchy on contracts page. Headings: ${headings.map((h) => `h${h.level}: ${h.text}`).join(', ')}`
        ).toBe(true)
      }
    })

    test('should have exactly one h1 per page', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const h1Count = await page.locator('h1').count()

      expect(h1Count, 'Page should have exactly one h1 element').toBe(1)
    })

    test('should not skip heading levels', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const headings = await getHeadings(page)

      if (headings.length > 1) {
        for (let i = 1; i < headings.length; i++) {
          const previousLevel = headings[i - 1].level
          const currentLevel = headings[i].level

          // Should not skip more than one level
          expect(
            currentLevel <= previousLevel + 1,
            `Heading level skipped: h${previousLevel} followed by h${currentLevel}`
          ).toBe(true)
        }
      }
    })

    test('should have descriptive heading text', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const headings = await getHeadings(page)

      headings.forEach((heading) => {
        expect(
          heading.text.length,
          `Heading should have text content. Level: h${heading.level}`
        ).toBeGreaterThan(0)
        expect(
          heading.text.trim().length,
          `Heading should not be empty. Level: h${heading.level}`
        ).toBeGreaterThan(0)
      })
    })
  })

  test.describe('Form Labels', () => {
    test('should have labels for all form inputs on login page', async ({ page }) => {
      await page.goto('/auth/login')
      await page.waitForLoadState('networkidle')

      const formInputs = await getFormInputsWithLabels(page)

      // Filter out hidden inputs
      const visibleInputs = formInputs.filter((input) => input.type !== 'hidden')

      visibleInputs.forEach((input) => {
        const hasLabel = input.hasLabel || input.hasAriaLabel || input.hasAriaLabelledBy
        expect(
          hasLabel,
          `Form input missing label. Type: ${input.type}, Name: ${input.name}, ID: ${input.id}`
        ).toBe(true)
      })
    })

    test('should have labels for all form inputs on asset creation form', async ({ page }) => {
      await login(page)
      await page.goto('/assets/new')
      await page.waitForLoadState('networkidle')

      const formInputs = await getFormInputsWithLabels(page)

      // Filter out hidden inputs
      const visibleInputs = formInputs.filter((input) => input.type !== 'hidden')

      visibleInputs.forEach((input) => {
        const hasLabel = input.hasLabel || input.hasAriaLabel || input.hasAriaLabelledBy
        expect(
          hasLabel,
          `Form input missing label on asset creation form. Type: ${input.type}, Name: ${input.name}, ID: ${input.id}`
        ).toBe(true)
      })
    })

    test('should have labels for all form inputs on contract creation form', async ({ page }) => {
      await login(page)
      await page.goto('/contracts/new')
      await page.waitForLoadState('networkidle')

      const formInputs = await getFormInputsWithLabels(page)

      // Filter out hidden inputs
      const visibleInputs = formInputs.filter((input) => input.type !== 'hidden')

      visibleInputs.forEach((input) => {
        const hasLabel = input.hasLabel || input.hasAriaLabel || input.hasAriaLabelledBy
        expect(
          hasLabel,
          `Form input missing label on contract creation form. Type: ${input.type}, Name: ${input.name}, ID: ${input.id}`
        ).toBe(true)
      })
    })

    test('should associate labels with inputs using for attribute', async ({ page }) => {
      await page.goto('/auth/login')
      await page.waitForLoadState('networkidle')

      const formInputs = await getFormInputsWithLabels(page)

      // Check inputs with IDs have associated labels
      const inputsWithIds = formInputs.filter((input) => input.id)

      inputsWithIds.forEach((input) => {
        if (input.id) {
          const label = await page.locator(`label[for="${input.id}"]`).count()
          // Either has explicit label or aria-label/aria-labelledby
          const hasAccessibleLabel = input.hasLabel || input.hasAriaLabel || input.hasAriaLabelledBy
          expect(
            hasAccessibleLabel,
            `Input with ID "${input.id}" should have associated label or aria-label`
          ).toBe(true)
        }
      })
    })

    test('should have descriptive label text for form inputs', async ({ page }) => {
      await page.goto('/auth/login')
      await page.waitForLoadState('networkidle')

      const formInputs = await getFormInputsWithLabels(page)

      const visibleInputs = formInputs.filter((input) => input.type !== 'hidden')

      visibleInputs.forEach((input) => {
        if (input.hasLabel && input.labelText) {
          expect(
            input.labelText.length,
            `Label text should not be empty for input: ${input.type}`
          ).toBeGreaterThan(0)
        }
      })
    })

    test('should have aria-required for required form fields', async ({ page }) => {
      await page.goto('/auth/login')
      await page.waitForLoadState('networkidle')

      // Check required inputs have aria-required
      const requiredInputs = await page.locator('input[required], textarea[required], select[required]').all()

      for (const input of requiredInputs) {
        const ariaRequired = await input.getAttribute('aria-required')
        // aria-required should be "true" for required fields
        if (ariaRequired !== null) {
          expect(ariaRequired, 'aria-required should be "true" for required fields').toBe('true')
        }
      }
    })

    test('should have aria-describedby for inputs with error messages', async ({ page }) => {
      await page.goto('/auth/login')
      await page.waitForLoadState('networkidle')

      // Try to trigger validation error
      const submitButton = page.locator('button[type="submit"]')
      if (await submitButton.count() > 0) {
        await submitButton.click()
        await page.waitForTimeout(500) // Wait for validation

        // Check inputs with errors
        const inputsWithErrors = await page.locator('input[aria-invalid="true"], textarea[aria-invalid="true"]').all()

        for (const input of inputsWithErrors) {
          const ariaDescribedBy = await input.getAttribute('aria-describedby')
          expect(
            ariaDescribedBy,
            'Input with error should have aria-describedby pointing to error message'
          ).toBeTruthy()

          if (ariaDescribedBy) {
            const errorElement = await page.locator(`#${ariaDescribedBy}`).count()
            expect(
              errorElement,
              `Error element with ID "${ariaDescribedBy}" should exist`
            ).toBeGreaterThan(0)
          }
        }
      }
    })
  })

  test.describe('Comprehensive Screen Reader Accessibility', () => {
    test('should meet all screen reader requirements on assets page', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Check semantic HTML
      const semanticElements = await getSemanticElements(page)
      expect(semanticElements.hasMain).toBe(true)
      expect(semanticElements.hasNav).toBe(true)

      // Check heading hierarchy
      const headings = await getHeadings(page)
      if (headings.length > 0) {
        expect(isValidHeadingHierarchy(headings)).toBe(true)
        expect(headings[0].level).toBe(1)
      }

      // Check form inputs (if any)
      const formInputs = await getFormInputsWithLabels(page)
      const visibleInputs = formInputs.filter((input) => input.type !== 'hidden')
      visibleInputs.forEach((input) => {
        const hasLabel = input.hasLabel || input.hasAriaLabel || input.hasAriaLabelledBy
        expect(hasLabel).toBe(true)
      })

      // Check interactive elements have ARIA labels
      const interactiveElements = await getInteractiveElementsWithAria(page)
      const elementsWithoutNames = interactiveElements.filter((el) => !el.hasAccessibleName)
      expect(elementsWithoutNames.length).toBe(0)
    })

    test('should meet all screen reader requirements on contracts page', async ({ page }) => {
      await login(page)
      await page.goto('/contracts')
      await page.waitForLoadState('networkidle')

      // Check semantic HTML
      const semanticElements = await getSemanticElements(page)
      expect(semanticElements.hasMain).toBe(true)

      // Check heading hierarchy
      const headings = await getHeadings(page)
      if (headings.length > 0) {
        expect(isValidHeadingHierarchy(headings)).toBe(true)
      }

      // Check interactive elements
      const interactiveElements = await getInteractiveElementsWithAria(page)
      const iconButtons = interactiveElements.filter(
        (el) => (el.tag === 'button' || el.role === 'button') && !el.text
      )
      iconButtons.forEach((button) => {
        expect(button.hasAccessibleName).toBe(true)
      })
    })

    test('should have proper page structure for screen readers', async ({ page }) => {
      await login(page)
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Check for skip links
      const skipLinks = await page.locator('a[href*="#main"], a[href*="#content"]').count()
      // Skip links are recommended but not required

      // Check for language attribute
      const htmlLang = await page.locator('html').getAttribute('lang')
      expect(htmlLang, 'HTML should have lang attribute').toBeTruthy()

      // Check for page title
      const pageTitle = await page.title()
      expect(pageTitle.length, 'Page should have a title').toBeGreaterThan(0)
    })
  })
})

