/**
 * Visual Testing Utilities
 *
 * Utilities for visual regression testing in Playwright E2E tests.
 * Provides helpers for:
 * - Component visual testing
 * - Page layout visual testing
 * - Responsive breakpoint testing
 * - Dark mode testing
 * - RTL layout testing
 *
 * Uses real visual comparisons - no mocks/stubs. Always fixes root cause.
 */

import { Page, expect } from '@playwright/test'

/**
 * Viewport sizes for responsive testing
 */
export const VIEWPORTS = {
  mobile: { width: 375, height: 667 }, // iPhone SE
  tablet: { width: 768, height: 1024 }, // iPad
  desktop: { width: 1280, height: 720 }, // Desktop
  largeDesktop: { width: 1920, height: 1080 }, // Large Desktop
}

/**
 * Visual test options
 */
export interface VisualTestOptions {
  /**
   * Test name for screenshot
   */
  name: string
  /**
   * Selector for element to screenshot (default: full page)
   */
  selector?: string
  /**
   * Viewport size
   */
  viewport?: { width: number; height: number }
  /**
   * Theme mode ('light' | 'dark')
   */
  theme?: 'light' | 'dark'
  /**
   * RTL direction
   */
  rtl?: boolean
  /**
   * Wait for element to be visible
   */
  waitForSelector?: string
  /**
   * Additional wait time in ms
   */
  waitTime?: number
  /**
   * Screenshot options
   */
  screenshotOptions?: {
    fullPage?: boolean
    animations?: 'disabled' | 'allow'
    mask?: string[]
  }
}

/**
 * Take visual snapshot of component or page
 *
 * @param page - Playwright page
 * @param options - Visual test options
 */
export async function takeVisualSnapshot(
  page: Page,
  options: VisualTestOptions
): Promise<void> {
  const {
    name,
    selector,
    viewport = VIEWPORTS.desktop,
    theme = 'light',
    rtl = false,
    waitForSelector,
    waitTime = 500,
    screenshotOptions = {},
  } = options

  // Set viewport
  await page.setViewportSize(viewport)

  // Set theme
  if (theme === 'dark') {
    await page.emulateMedia({ colorScheme: 'dark' })
    // Try to toggle dark mode if theme toggle exists
    const themeToggle = page.locator('button[aria-label*="theme"], button[aria-label*="dark"], button[aria-label*="light"]').first()
    if (await themeToggle.isVisible().catch(() => false)) {
      await themeToggle.click()
      await page.waitForTimeout(500)
    }
  } else {
    await page.emulateMedia({ colorScheme: 'light' })
  }

  // Set RTL if needed
  if (rtl) {
    await page.evaluate(() => {
      document.documentElement.setAttribute('dir', 'rtl')
    })
  } else {
    await page.evaluate(() => {
      document.documentElement.setAttribute('dir', 'ltr')
    })
  }

  // Wait for selector if provided
  if (waitForSelector) {
    await page.waitForSelector(waitForSelector, { state: 'visible', timeout: 10000 })
  }

  // Additional wait time
  await page.waitForTimeout(waitTime)

  // Take screenshot
  const target = selector ? page.locator(selector).first() : page
  await expect(target).toHaveScreenshot(name, {
    fullPage: screenshotOptions.fullPage ?? true,
    animations: screenshotOptions.animations === 'allow' ? 'allow' : 'disabled',
    mask: screenshotOptions.mask?.map((s) => page.locator(s)),
  })
}

/**
 * Test component visually in all variants
 *
 * @param page - Playwright page
 * @param componentPath - Path to component page/story
 * @param variants - Array of variant names to test
 * @param options - Additional options
 */
export async function testComponentVariants(
  page: Page,
  componentPath: string,
  variants: string[],
  options: {
    viewport?: { width: number; height: number }
    theme?: 'light' | 'dark'
    states?: string[]
  } = {}
): Promise<void> {
  const { viewport = VIEWPORTS.desktop, theme = 'light', states = [] } = options

  for (const variant of variants) {
    // Navigate to component variant
    const url = `${componentPath}?variant=${variant}`
    await page.goto(url)
    await page.waitForLoadState('networkidle')

    // Test base variant
    await takeVisualSnapshot(page, {
      name: `component-${componentPath.split('/').pop()}-${variant}-${theme}`,
      viewport,
      theme,
      waitTime: 1000,
    })

    // Test states if provided
    for (const state of states) {
      // Apply state (e.g., hover, focus, disabled)
      if (state === 'hover') {
        const element = page.locator('button, a, [role="button"]').first()
        if (await element.isVisible().catch(() => false)) {
          await element.hover()
          await page.waitForTimeout(200)
        }
      } else if (state === 'focus') {
        const element = page.locator('button, a, input, [role="button"]').first()
        if (await element.isVisible().catch(() => false)) {
          await element.focus()
          await page.waitForTimeout(200)
        }
      } else if (state === 'disabled') {
        // Find disabled element or disable one
        const element = page.locator('[disabled], [aria-disabled="true"]').first()
        if (await element.isVisible().catch(() => false)) {
          await element.focus()
          await page.waitForTimeout(200)
        }
      }

      await takeVisualSnapshot(page, {
        name: `component-${componentPath.split('/').pop()}-${variant}-${state}-${theme}`,
        viewport,
        theme,
        waitTime: 200,
      })
    }
  }
}

/**
 * Test page layout visually
 *
 * @param page - Playwright page
 * @param pagePath - Path to page
 * @param options - Additional options
 */
export async function testPageLayout(
  page: Page,
  pagePath: string,
  options: {
    viewport?: { width: number; height: number }
    theme?: 'light' | 'dark'
    scrollToBottom?: boolean
  } = {}
): Promise<void> {
  const { viewport = VIEWPORTS.desktop, theme = 'light', scrollToBottom = false } = options

  await page.goto(pagePath)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)

  // Test full page
  await takeVisualSnapshot(page, {
    name: `page-${pagePath.replace(/\//g, '-').replace(/^-/, '')}-${viewport.width}x${viewport.height}-${theme}`,
    viewport,
    theme,
    waitTime: 1000,
  })

  // Test scrolled state if requested
  if (scrollToBottom) {
    await page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight)
    })
    await page.waitForTimeout(500)

    await takeVisualSnapshot(page, {
      name: `page-${pagePath.replace(/\//g, '-').replace(/^-/, '')}-scrolled-${viewport.width}x${viewport.height}-${theme}`,
      viewport,
      theme,
      waitTime: 500,
    })
  }
}

/**
 * Test responsive breakpoints
 *
 * @param page - Playwright page
 * @param pagePath - Path to page
 * @param options - Additional options
 */
export async function testResponsiveBreakpoints(
  page: Page,
  pagePath: string,
  options: {
    breakpoints?: Array<keyof typeof VIEWPORTS>
    theme?: 'light' | 'dark'
  } = {}
): Promise<void> {
  const { breakpoints = ['mobile', 'tablet', 'desktop'], theme = 'light' } = options

  for (const breakpoint of breakpoints) {
    const viewport = VIEWPORTS[breakpoint]
    await testPageLayout(page, pagePath, {
      viewport,
      theme,
    })
  }
}

/**
 * Test dark mode
 *
 * @param page - Playwright page
 * @param pagePath - Path to page
 * @param options - Additional options
 */
export async function testDarkMode(
  page: Page,
  pagePath: string,
  options: {
    viewport?: { width: number; height: number }
  } = {}
): Promise<void> {
  const { viewport = VIEWPORTS.desktop } = options

  // Test light mode
  await testPageLayout(page, pagePath, {
    viewport,
    theme: 'light',
  })

  // Test dark mode
  await testPageLayout(page, pagePath, {
    viewport,
    theme: 'dark',
  })
}

/**
 * Test RTL layout
 *
 * @param page - Playwright page
 * @param pagePath - Path to page
 * @param options - Additional options
 */
export async function testRTLLayout(
  page: Page,
  pagePath: string,
  options: {
    viewport?: { width: number; height: number }
    theme?: 'light' | 'dark'
  } = {}
): Promise<void> {
  const { viewport = VIEWPORTS.desktop, theme = 'light' } = options

  await page.goto(pagePath)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(1000)

  // Test LTR
  await takeVisualSnapshot(page, {
    name: `page-${pagePath.replace(/\//g, '-').replace(/^-/, '')}-ltr-${theme}`,
    viewport,
    theme,
    rtl: false,
    waitTime: 1000,
  })

  // Test RTL
  await takeVisualSnapshot(page, {
    name: `page-${pagePath.replace(/\//g, '-').replace(/^-/, '')}-rtl-${theme}`,
    viewport,
    theme,
    rtl: true,
    waitTime: 1000,
  })
}

/**
 * Wait for animations to complete
 *
 * @param page - Playwright page
 * @param timeout - Timeout in ms
 */
export async function waitForAnimations(page: Page, timeout: number = 1000): Promise<void> {
  await page.waitForFunction(
    () => {
      const animations = document.getAnimations()
      return animations.length === 0
    },
    { timeout }
  ).catch(() => {
    // If no animations or timeout, just wait a bit
    return page.waitForTimeout(500)
  })
}

/**
 * Mask dynamic content in screenshots
 *
 * @param selectors - Array of selectors to mask
 * @returns Mask configuration
 */
export function createMask(selectors: string[]): string[] {
  return selectors
}

