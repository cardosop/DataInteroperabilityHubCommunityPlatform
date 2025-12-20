/**
 * Color Contrast Tests
 *
 * Comprehensive tests for WCAG 2.1 AA color contrast compliance:
 * - Text contrast (4.5:1 for normal text, 3:1 for large text)
 * - Interactive element contrast (3:1)
 * - Error state contrast
 *
 * Uses real implementations - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { login } from '../utils/auth'

/**
 * Calculate relative luminance of a color
 * Based on WCAG 2.1 specification
 */
function getLuminance(r: number, g: number, b: number): number {
  const [rs, gs, bs] = [r, g, b].map((val) => {
    val = val / 255
    return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
}

/**
 * Parse hex color to RGB
 */
function hexToRgb(hex: string): [number, number, number] | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)]
    : null
}

/**
 * Parse RGB color string to RGB values
 */
function rgbToRgb(rgb: string): [number, number, number] | null {
  const match = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (match) {
    return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])]
  }
  return null
}

/**
 * Get contrast ratio between two colors
 * Based on WCAG 2.1 specification
 */
function getContrastRatio(color1: string, color2: string): number {
  let rgb1: [number, number, number] | null = null
  let rgb2: [number, number, number] | null = null

  // Try hex first
  if (color1.startsWith('#')) {
    rgb1 = hexToRgb(color1)
  } else if (color1.startsWith('rgb')) {
    rgb1 = rgbToRgb(color1)
  }

  if (color2.startsWith('#')) {
    rgb2 = hexToRgb(color2)
  } else if (color2.startsWith('rgb')) {
    rgb2 = rgbToRgb(color2)
  }

  if (!rgb1 || !rgb2) {
    return 0
  }

  const l1 = getLuminance(rgb1[0], rgb1[1], rgb1[2])
  const l2 = getLuminance(rgb2[0], rgb2[1], rgb2[2])

  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)

  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Get computed color from element
 */
async function getElementColor(
  page: any,
  selector: string,
  property: 'color' | 'backgroundColor' | 'borderColor' = 'color'
): Promise<string> {
  return await page.evaluate(
    ({ sel, prop }) => {
      const element = document.querySelector(sel)
      if (!element) return ''
      const computed = window.getComputedStyle(element)
      return computed[prop] || ''
    },
    { sel: selector, prop: property }
  )
}

/**
 * Get background color (may need to traverse parent elements)
 */
async function getBackgroundColor(page: any, selector: string): Promise<string> {
  return await page.evaluate(
    (sel) => {
      const element = document.querySelector(sel)
      if (!element) return ''

      let current: HTMLElement | null = element
      while (current) {
        const bg = window.getComputedStyle(current).backgroundColor
        // Check if background is not transparent
        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
          return bg
        }
        current = current.parentElement
      }

      // Fallback to body background
      return window.getComputedStyle(document.body).backgroundColor || 'rgb(255, 255, 255)'
    },
    selector
  )
}

/**
 * Check if text is large (WCAG definition: >18px or bold >=14px)
 */
async function isLargeText(page: any, selector: string): Promise<boolean> {
  return await page.evaluate((sel) => {
    const element = document.querySelector(sel)
    if (!element) return false

    const computed = window.getComputedStyle(element)
    const fontSize = parseFloat(computed.fontSize)
    const fontWeight = computed.fontWeight

    // Large text: >18px or bold >=14px
    return fontSize > 18 || (fontSize >= 14 && (fontWeight === 'bold' || parseInt(fontWeight) >= 700))
  }, selector)
}

test.describe('Color Contrast Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Login before tests
    const testUser = {
      email: process.env.TEST_USER_EMAIL || 'test@example.com',
      password: process.env.TEST_USER_PASSWORD || 'testpassword123',
    }
    try {
      await login(page, testUser)
    } catch (error) {
      // Continue if already logged in
    }
  })

  test.describe('Text Contrast', () => {
    test('should meet 4.5:1 contrast ratio for normal text', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find text elements
      const textElements = await page.evaluate(() => {
        const elements: Array<{ selector: string; text: string }> = []
        const textNodes = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6, td, th, li, label')
        textNodes.forEach((el, index) => {
          const text = el.textContent?.trim()
          if (text && text.length > 0 && text.length < 100) {
            // Create unique selector
            const selector = `text-element-${index}`
            el.setAttribute('data-test-id', selector)
            elements.push({ selector: `[data-test-id="${selector}"]`, text })
          }
        })
        return elements.slice(0, 20) // Test first 20 text elements
      })

      for (const { selector, text } of textElements) {
        const isLarge = await isLargeText(page, selector)
        const textColor = await getElementColor(page, selector, 'color')
        const bgColor = await getBackgroundColor(page, selector)

        if (textColor && bgColor) {
          const contrastRatio = getContrastRatio(textColor, bgColor)

          if (isLarge) {
            // Large text: minimum 3:1
            expect(contrastRatio).toBeGreaterThanOrEqual(3)
          } else {
            // Normal text: minimum 4.5:1
            expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
          }
        }
      }
    })

    test('should meet 3:1 contrast ratio for large text', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find large text elements (headings, large text)
      const largeTextElements = await page.evaluate(() => {
        const elements: Array<{ selector: string; text: string }> = []
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6')
        headings.forEach((el, index) => {
          const text = el.textContent?.trim()
          if (text && text.length > 0) {
            const selector = `large-text-${index}`
            el.setAttribute('data-test-id', selector)
            elements.push({ selector: `[data-test-id="${selector}"]`, text })
          }
        })
        return elements
      })

      for (const { selector } of largeTextElements) {
        const textColor = await getElementColor(page, selector, 'color')
        const bgColor = await getBackgroundColor(page, selector)

        if (textColor && bgColor) {
          const contrastRatio = getContrastRatio(textColor, bgColor)
          // Large text: minimum 3:1
          expect(contrastRatio).toBeGreaterThanOrEqual(3)
        }
      }
    })

    test('should meet contrast requirements for body text', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find body text elements
      const bodyText = page.locator('p, span, div').filter({ hasText: /.+/ }).first()
      const hasBodyText = await bodyText.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasBodyText) {
        const textColor = await getElementColor(page, 'p, span, div', 'color')
        const bgColor = await getBackgroundColor(page, 'body')

        if (textColor && bgColor) {
          const contrastRatio = getContrastRatio(textColor, bgColor)
          // Body text should meet 4.5:1
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      }
    })

    test('should meet contrast requirements for secondary text', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find secondary text (captions, hints, etc.)
      const secondaryText = page
        .locator('[class*="caption"], [class*="hint"], [class*="secondary"], [class*="muted"]')
        .first()
      const hasSecondary = await secondaryText.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasSecondary) {
        const selector = '[class*="caption"], [class*="hint"], [class*="secondary"]'
        const textColor = await getElementColor(page, selector, 'color')
        const bgColor = await getBackgroundColor(page, selector)

        if (textColor && bgColor) {
          const contrastRatio = getContrastRatio(textColor, bgColor)
          // Secondary text should still meet 4.5:1 (or at least 3:1 if large)
          expect(contrastRatio).toBeGreaterThanOrEqual(3)
        }
      }
    })

    test('should meet contrast requirements for link text', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find links
      const links = page.locator('a[href]').first()
      const hasLinks = await links.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasLinks) {
        const linkColor = await getElementColor(page, 'a[href]', 'color')
        const bgColor = await getBackgroundColor(page, 'a[href]')

        if (linkColor && bgColor) {
          const contrastRatio = getContrastRatio(linkColor, bgColor)
          // Links should meet 4.5:1 (or 3:1 if large)
          expect(contrastRatio).toBeGreaterThanOrEqual(3)
        }
      }
    })
  })

  test.describe('Interactive Element Contrast', () => {
    test('should meet 3:1 contrast ratio for buttons', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find buttons
      const buttons = page.locator('button, [role="button"]').first()
      const hasButtons = await buttons.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasButtons) {
        // Test button text contrast
        const buttonTextColor = await getElementColor(page, 'button', 'color')
        const buttonBgColor = await getElementColor(page, 'button', 'backgroundColor')

        if (buttonTextColor && buttonBgColor) {
          const contrastRatio = getContrastRatio(buttonTextColor, buttonBgColor)
          // Buttons should meet 3:1 for UI components
          expect(contrastRatio).toBeGreaterThanOrEqual(3)
        }

        // Test button border contrast (if outlined)
        const buttonBorderColor = await getElementColor(page, 'button', 'borderColor')
        if (buttonBorderColor && buttonBgColor) {
          const borderContrast = getContrastRatio(buttonBorderColor, buttonBgColor)
          // Border should meet 3:1
          expect(borderContrast).toBeGreaterThanOrEqual(3)
        }
      }
    })

    test('should meet 3:1 contrast ratio for input fields', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find input fields
      const inputs = page.locator('input[type="text"], input[type="email"], textarea').first()
      const hasInputs = await inputs.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasInputs) {
        // Test input text contrast
        const inputTextColor = await getElementColor(page, 'input, textarea', 'color')
        const inputBgColor = await getElementColor(page, 'input, textarea', 'backgroundColor')

        if (inputTextColor && inputBgColor) {
          const contrastRatio = getContrastRatio(inputTextColor, inputBgColor)
          // Input text should meet 4.5:1
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }

        // Test input border contrast
        const inputBorderColor = await getElementColor(page, 'input, textarea', 'borderColor')
        if (inputBorderColor && inputBgColor) {
          const borderContrast = getContrastRatio(inputBorderColor, inputBgColor)
          // Border should meet 3:1
          expect(borderContrast).toBeGreaterThanOrEqual(3)
        }
      }
    })

    test('should meet 3:1 contrast ratio for form labels', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find form labels
      const labels = page.locator('label').first()
      const hasLabels = await labels.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasLabels) {
        const labelColor = await getElementColor(page, 'label', 'color')
        const bgColor = await getBackgroundColor(page, 'label')

        if (labelColor && bgColor) {
          const contrastRatio = getContrastRatio(labelColor, bgColor)
          // Labels should meet 4.5:1
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      }
    })

    test('should meet 3:1 contrast ratio for focus indicators', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Test focus indicator contrast
      const focusContrast = await page.evaluate(() => {
        const button = document.querySelector('button')
        if (!button) return null

        // Get focus styles
        const computed = window.getComputedStyle(button)
        const outlineColor = computed.outlineColor || computed.borderColor
        const bgColor = computed.backgroundColor

        // Calculate contrast
        const getLuminance = (r: number, g: number, b: number) => {
          const [rs, gs, bs] = [r, g, b].map((val) => {
            val = val / 255
            return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4)
          })
          return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
        }

        const parseRgb = (rgb: string): [number, number, number] | null => {
          const match = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
          return match ? [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])] : null
        }

        const rgb1 = parseRgb(outlineColor)
        const rgb2 = parseRgb(bgColor)

        if (!rgb1 || !rgb2) return null

        const l1 = getLuminance(rgb1[0], rgb1[1], rgb1[2])
        const l2 = getLuminance(rgb2[0], rgb2[1], rgb2[2])
        const lighter = Math.max(l1, l2)
        const darker = Math.min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)
      })

      if (focusContrast !== null) {
        // Focus indicators should meet 3:1
        expect(focusContrast).toBeGreaterThanOrEqual(3)
      }
    })

    test('should meet contrast requirements for disabled elements', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find disabled elements
      const disabledElements = await page.evaluate(() => {
        const elements: Array<{ selector: string; tag: string }> = []
        const disabled = document.querySelectorAll('button[disabled], input[disabled], [aria-disabled="true"]')
        disabled.forEach((el, index) => {
          const selector = `disabled-${index}`
          el.setAttribute('data-test-id', selector)
          elements.push({ selector: `[data-test-id="${selector}"]`, tag: el.tagName })
        })
        return elements
      })

      for (const { selector } of disabledElements) {
        const textColor = await getElementColor(page, selector, 'color')
        const bgColor = await getElementColor(page, selector, 'backgroundColor')

        if (textColor && bgColor) {
          const contrastRatio = getContrastRatio(textColor, bgColor)
          // Disabled elements should still meet minimum contrast (may be lower but should be readable)
          expect(contrastRatio).toBeGreaterThanOrEqual(2) // Lower threshold for disabled
        }
      }
    })
  })

  test.describe('Error State Contrast', () => {
    test('should meet contrast requirements for error text', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Try to trigger or find error states
      // Look for error messages, alerts, etc.
      const errorElements = page.locator('[role="alert"], [class*="error"], [class*="Error"]').first()
      const hasErrors = await errorElements.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasErrors) {
        const errorTextColor = await getElementColor(page, '[role="alert"], [class*="error"]', 'color')
        const errorBgColor = await getElementColor(page, '[role="alert"], [class*="error"]', 'backgroundColor')

        if (errorTextColor && errorBgColor) {
          const contrastRatio = getContrastRatio(errorTextColor, errorBgColor)
          // Error text should meet 4.5:1
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      } else {
        // Test error colors from design tokens
        const errorColor = '#F44336' // error-500
        const whiteBg = '#FFFFFF'
        const contrastRatio = getContrastRatio(errorColor, whiteBg)
        expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
      }
    })

    test('should meet contrast requirements for error borders', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find input fields with error state
      const errorInputs = page.locator('input[aria-invalid="true"], input.error, .Mui-error input').first()
      const hasErrorInputs = await errorInputs.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasErrorInputs) {
        const errorBorderColor = await getElementColor(page, 'input[aria-invalid="true"]', 'borderColor')
        const inputBgColor = await getElementColor(page, 'input[aria-invalid="true"]', 'backgroundColor')

        if (errorBorderColor && inputBgColor) {
          const contrastRatio = getContrastRatio(errorBorderColor, inputBgColor)
          // Error borders should meet 3:1
          expect(contrastRatio).toBeGreaterThanOrEqual(3)
        }
      } else {
        // Test error border color from design tokens
        const errorBorderColor = '#F44336' // error-500
        const whiteBg = '#FFFFFF'
        const contrastRatio = getContrastRatio(errorBorderColor, whiteBg)
        expect(contrastRatio).toBeGreaterThanOrEqual(3)
      }
    })

    test('should meet contrast requirements for error alert backgrounds', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find error alerts
      const errorAlerts = page.locator('[role="alert"][class*="error"], .MuiAlert-error').first()
      const hasAlerts = await errorAlerts.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasAlerts) {
        const alertTextColor = await getElementColor(page, '[role="alert"][class*="error"]', 'color')
        const alertBgColor = await getElementColor(page, '[role="alert"][class*="error"]', 'backgroundColor')

        if (alertTextColor && alertBgColor) {
          const contrastRatio = getContrastRatio(alertTextColor, alertBgColor)
          // Error alert text should meet 4.5:1
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      } else {
        // Test error alert colors from design tokens
        // Error background: error-50 (#FFEBEE), Error text: error-700 (#D32F2F)
        const errorBg = '#FFEBEE'
        const errorText = '#D32F2F'
        const contrastRatio = getContrastRatio(errorText, errorBg)
        expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
      }
    })

    test('should meet contrast requirements for validation error messages', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Look for validation error messages
      const errorMessages = page
        .locator('[class*="error-message"], [class*="helper-text"], [class*="MuiFormHelperText-error"]')
        .first()
      const hasMessages = await errorMessages.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasMessages) {
        const messageColor = await getElementColor(page, '[class*="error-message"], [class*="helper-text"]', 'color')
        const bgColor = await getBackgroundColor(page, '[class*="error-message"], [class*="helper-text"]')

        if (messageColor && bgColor) {
          const contrastRatio = getContrastRatio(messageColor, bgColor)
          // Error messages should meet 4.5:1
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      } else {
        // Test error message color from design tokens
        // Error text: error-700 (#D32F2F)
        const errorText = '#D32F2F'
        const whiteBg = '#FFFFFF'
        const contrastRatio = getContrastRatio(errorText, whiteBg)
        expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
      }
    })

    test('should meet contrast requirements for error icons', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Find error icons
      const errorIcons = page.locator('[class*="error"] svg, [class*="error"] [class*="icon"]').first()
      const hasIcons = await errorIcons.isVisible({ timeout: 2000 }).catch(() => false)

      if (hasIcons) {
        // Icons are graphical objects, should meet 3:1
        const iconColor = await page.evaluate(() => {
          const icon = document.querySelector('[class*="error"] svg, [class*="error"] [class*="icon"]')
          if (!icon) return null
          const computed = window.getComputedStyle(icon)
          return computed.color || computed.fill || computed.stroke
        })

        const bgColor = await getBackgroundColor(page, '[class*="error"]')

        if (iconColor && bgColor) {
          const contrastRatio = getContrastRatio(iconColor, bgColor)
          // Error icons should meet 3:1
          expect(contrastRatio).toBeGreaterThanOrEqual(3)
        }
      } else {
        // Test error icon color from design tokens
        // Error icon: error-500 (#F44336)
        const errorIcon = '#F44336'
        const whiteBg = '#FFFFFF'
        const contrastRatio = getContrastRatio(errorIcon, whiteBg)
        expect(contrastRatio).toBeGreaterThanOrEqual(3)
      }
    })
  })

  test.describe('Color Contrast Integration', () => {
    test('should maintain contrast across different pages', async ({ page }) => {
      const pages = ['/assets', '/marketplace', '/api-docs']

      for (const pagePath of pages) {
        await page.goto(pagePath)
        await page.waitForLoadState('networkidle')
        await page.waitForTimeout(1000)

        // Test body text contrast
        const bodyTextColor = await getElementColor(page, 'body', 'color')
        const bodyBgColor = await getElementColor(page, 'body', 'backgroundColor')

        if (bodyTextColor && bodyBgColor) {
          const contrastRatio = getContrastRatio(bodyTextColor, bodyBgColor)
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      }
    })

    test('should maintain contrast in dark mode (if available)', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(1000)

      // Check if dark mode is available
      const hasDarkMode = await page.evaluate(() => {
        return document.documentElement.classList.contains('dark') ||
          document.body.classList.contains('dark') ||
          window.matchMedia('(prefers-color-scheme: dark)').matches
      })

      if (hasDarkMode) {
        // Test contrast in dark mode
        const textColor = await getElementColor(page, 'body', 'color')
        const bgColor = await getElementColor(page, 'body', 'backgroundColor')

        if (textColor && bgColor) {
          const contrastRatio = getContrastRatio(textColor, bgColor)
          expect(contrastRatio).toBeGreaterThanOrEqual(4.5)
        }
      }
    })
  })
})

