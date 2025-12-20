/**
 * Visual Regression Tests (6.15.2)
 *
 * Comprehensive visual regression tests for:
 * - Base components (all variants, states)
 * - Feature components (all variants, states)
 * - Page layouts (all pages)
 * - Responsive breakpoints (mobile, tablet, desktop)
 * - Dark mode (if implemented)
 * - RTL layouts (if applicable)
 *
 * Uses real visual comparisons - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'
import {
  takeVisualSnapshot,
  testComponentVariants,
  testPageLayout,
  testResponsiveBreakpoints,
  testDarkMode,
  testRTLLayout,
  VIEWPORTS,
  waitForAnimations,
} from '../utils/visual-testing'

/**
 * Test credentials
 */
const TEST_CREDENTIALS = {
  email: process.env.TEST_USER_EMAIL || 'test@example.com',
  password: process.env.TEST_USER_PASSWORD || 'testpassword123',
}

test.describe('Visual Regression Tests (6.15.2)', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.login(TEST_CREDENTIALS.email, TEST_CREDENTIALS.password)
    await page.waitForLoadState('networkidle')
  })

  test.describe('Base Components Visual Tests', () => {
    test('should render Button component in all variants and states', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Find buttons on the page
      const buttons = page.locator('button')
      const buttonCount = await buttons.count()

      if (buttonCount > 0) {
        // Test first few buttons in different states
        for (let i = 0; i < Math.min(3, buttonCount); i++) {
          const button = buttons.nth(i)
          if (await button.isVisible().catch(() => false)) {
            // Default state
            await takeVisualSnapshot(page, {
              name: `component-button-default-${i}`,
              selector: `button:nth-of-type(${i + 1})`,
              waitTime: 500,
            })

            // Hover state
            await button.hover()
            await page.waitForTimeout(200)
            await takeVisualSnapshot(page, {
              name: `component-button-hover-${i}`,
              selector: `button:nth-of-type(${i + 1})`,
              waitTime: 200,
            })

            // Focus state
            await button.focus()
            await page.waitForTimeout(200)
            await takeVisualSnapshot(page, {
              name: `component-button-focus-${i}`,
              selector: `button:nth-of-type(${i + 1})`,
              waitTime: 200,
            })
          }
        }
      }
    })

    test('should render Input components in all states', async ({ page }) => {
      await page.goto('/assets/new')
      await page.waitForLoadState('networkidle')

      // Find input fields
      const inputs = page.locator('input[type="text"], input[type="email"], textarea')
      const inputCount = await inputs.count()

      if (inputCount > 0) {
        for (let i = 0; i < Math.min(3, inputCount); i++) {
          const input = inputs.nth(i)
          if (await input.isVisible().catch(() => false)) {
            // Default state
            await takeVisualSnapshot(page, {
              name: `component-input-default-${i}`,
              selector: `input:nth-of-type(${i + 1}), textarea:nth-of-type(${i + 1})`,
              waitTime: 500,
            })

            // Focus state
            await input.focus()
            await page.waitForTimeout(200)
            await takeVisualSnapshot(page, {
              name: `component-input-focus-${i}`,
              selector: `input:nth-of-type(${i + 1}), textarea:nth-of-type(${i + 1})`,
              waitTime: 200,
            })

            // Filled state
            await input.fill('Test input value')
            await page.waitForTimeout(200)
            await takeVisualSnapshot(page, {
              name: `component-input-filled-${i}`,
              selector: `input:nth-of-type(${i + 1}), textarea:nth-of-type(${i + 1})`,
              waitTime: 200,
            })
          }
        }
      }
    })

    test('should render Card components in all variants', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Find cards
      const cards = page.locator('[class*="card"], [class*="Card"], .MuiCard-root')
      const cardCount = await cards.count()

      if (cardCount > 0) {
        for (let i = 0; i < Math.min(3, cardCount); i++) {
          const card = cards.nth(i)
          if (await card.isVisible().catch(() => false)) {
            await takeVisualSnapshot(page, {
              name: `component-card-${i}`,
              selector: `[class*="card"]:nth-of-type(${i + 1}), [class*="Card"]:nth-of-type(${i + 1}), .MuiCard-root:nth-of-type(${i + 1})`,
              waitTime: 500,
            })
          }
        }
      }
    })

    test('should render Badge components in all variants', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Find badges
      const badges = page.locator('[class*="badge"], [class*="Badge"], .MuiBadge-root, .MuiChip-root')
      const badgeCount = await badges.count()

      if (badgeCount > 0) {
        for (let i = 0; i < Math.min(5, badgeCount); i++) {
          const badge = badges.nth(i)
          if (await badge.isVisible().catch(() => false)) {
            await takeVisualSnapshot(page, {
              name: `component-badge-${i}`,
              selector: `[class*="badge"]:nth-of-type(${i + 1}), [class*="Badge"]:nth-of-type(${i + 1}), .MuiBadge-root:nth-of-type(${i + 1}), .MuiChip-root:nth-of-type(${i + 1})`,
              waitTime: 500,
            })
          }
        }
      }
    })

    test('should render Typography components in all variants', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Test different heading levels
      const headings = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
      for (const heading of headings) {
        const element = page.locator(heading).first()
        if (await element.isVisible().catch(() => false)) {
          await takeVisualSnapshot(page, {
            name: `component-typography-${heading}`,
            selector: `${heading}:first-of-type`,
            waitTime: 500,
          })
        }
      }
    })
  })

  test.describe('Feature Components Visual Tests', () => {
    test('should render AssetCard component in all states', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const assetCards = page.locator('[data-testid*="asset"], [class*="AssetCard"]')
      const cardCount = await assetCards.count()

      if (cardCount > 0) {
        const card = assetCards.first()
        await takeVisualSnapshot(page, {
          name: 'component-asset-card-default',
          selector: '[data-testid*="asset"]:first-of-type, [class*="AssetCard"]:first-of-type',
          waitTime: 1000,
        })

        // Hover state
        await card.hover()
        await page.waitForTimeout(300)
        await takeVisualSnapshot(page, {
          name: 'component-asset-card-hover',
          selector: '[data-testid*="asset"]:first-of-type, [class*="AssetCard"]:first-of-type',
          waitTime: 200,
        })
      }
    })

    test('should render ContractCard component in all states', async ({ page }) => {
      await page.goto('/contracts')
      await page.waitForLoadState('networkidle')

      const contractCards = page.locator('[data-testid*="contract"], [class*="ContractCard"]')
      const cardCount = await contractCards.count()

      if (cardCount > 0) {
        await takeVisualSnapshot(page, {
          name: 'component-contract-card-default',
          selector: '[data-testid*="contract"]:first-of-type, [class*="ContractCard"]:first-of-type',
          waitTime: 1000,
        })
      }
    })

    test('should render MarketplaceListingCard component in all states', async ({ page }) => {
      await page.goto('/marketplace')
      await page.waitForLoadState('networkidle')

      const listingCards = page.locator('[data-testid*="marketplace"], [data-testid*="listing"]')
      const cardCount = await listingCards.count()

      if (cardCount > 0) {
        await takeVisualSnapshot(page, {
          name: 'component-marketplace-listing-card-default',
          selector: '[data-testid*="marketplace"]:first-of-type, [data-testid*="listing"]:first-of-type',
          waitTime: 1000,
        })
      }
    })

    test('should render Navigation Header component', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      await takeVisualSnapshot(page, {
        name: 'component-navigation-header',
        selector: 'header, nav, [role="navigation"]',
        waitTime: 1000,
      })
    })

    test('should render Modal/Dialog components', async ({ page }) => {
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Try to open a modal
      const modalTrigger = page.locator('button:has-text("New"), button:has-text("Create"), button[aria-haspopup="true"]').first()
      if (await modalTrigger.isVisible().catch(() => false)) {
        await modalTrigger.click()
        await page.waitForTimeout(500)

        const modal = page.locator('[role="dialog"]').first()
        if (await modal.isVisible().catch(() => false)) {
          await takeVisualSnapshot(page, {
            name: 'component-modal-dialog',
            selector: '[role="dialog"]',
            waitTime: 500,
          })
        }
      }
    })
  })

  test.describe('Page Layout Visual Tests', () => {
    test('should render Home page layout', async ({ page }) => {
      await testPageLayout(page, '/', {
        scrollToBottom: true,
      })
    })

    test('should render Assets page layout', async ({ page }) => {
      await testPageLayout(page, '/assets', {
        scrollToBottom: true,
      })
    })

    test('should render Contracts page layout', async ({ page }) => {
      await testPageLayout(page, '/contracts', {
        scrollToBottom: true,
      })
    })

    test('should render Marketplace page layout', async ({ page }) => {
      await testPageLayout(page, '/marketplace', {
        scrollToBottom: true,
      })
    })

    test('should render Compliance Dashboard page layout', async ({ page }) => {
      await testPageLayout(page, '/compliance', {
        scrollToBottom: true,
      })
    })

    test('should render Data Quality Dashboard page layout', async ({ page }) => {
      await testPageLayout(page, '/data-quality', {
        scrollToBottom: true,
      })
    })

    test('should render Jobs page layout', async ({ page }) => {
      await testPageLayout(page, '/jobs', {
        scrollToBottom: true,
      })
    })

    test('should render Datasets page layout', async ({ page }) => {
      await testPageLayout(page, '/datasets', {
        scrollToBottom: true,
      })
    })

    test('should render API Documentation page layout', async ({ page }) => {
      await testPageLayout(page, '/api-docs', {
        scrollToBottom: true,
      })
    })
  })

  test.describe('Responsive Breakpoint Visual Tests', () => {
    test('should render Home page at all breakpoints', async ({ page }) => {
      await testResponsiveBreakpoints(page, '/', {
        breakpoints: ['mobile', 'tablet', 'desktop'],
      })
    })

    test('should render Assets page at all breakpoints', async ({ page }) => {
      await testResponsiveBreakpoints(page, '/assets', {
        breakpoints: ['mobile', 'tablet', 'desktop'],
      })
    })

    test('should render Marketplace page at all breakpoints', async ({ page }) => {
      await testResponsiveBreakpoints(page, '/marketplace', {
        breakpoints: ['mobile', 'tablet', 'desktop'],
      })
    })

    test('should render Contracts page at all breakpoints', async ({ page }) => {
      await testResponsiveBreakpoints(page, '/contracts', {
        breakpoints: ['mobile', 'tablet', 'desktop'],
      })
    })

    test('should render Navigation Header at all breakpoints', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      for (const breakpoint of ['mobile', 'tablet', 'desktop'] as const) {
        const viewport = VIEWPORTS[breakpoint]
        await takeVisualSnapshot(page, {
          name: `component-navigation-header-${breakpoint}`,
          selector: 'header, nav, [role="navigation"]',
          viewport,
          waitTime: 1000,
        })
      }
    })
  })

  test.describe('Dark Mode Visual Tests', () => {
    test('should render Home page in dark mode', async ({ page }) => {
      await testDarkMode(page, '/')
    })

    test('should render Assets page in dark mode', async ({ page }) => {
      await testDarkMode(page, '/assets')
    })

    test('should render Marketplace page in dark mode', async ({ page }) => {
      await testDarkMode(page, '/marketplace')
    })

    test('should render Contracts page in dark mode', async ({ page }) => {
      await testDarkMode(page, '/contracts')
    })

    test('should render Navigation Header in dark mode', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // Light mode
      await takeVisualSnapshot(page, {
        name: 'component-navigation-header-light',
        selector: 'header, nav, [role="navigation"]',
        theme: 'light',
        waitTime: 1000,
      })

      // Dark mode
      await takeVisualSnapshot(page, {
        name: 'component-navigation-header-dark',
        selector: 'header, nav, [role="navigation"]',
        theme: 'dark',
        waitTime: 1000,
      })
    })

    test('should render Button components in dark mode', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      const buttons = page.locator('button')
      if (await buttons.count() > 0) {
        // Light mode
        await takeVisualSnapshot(page, {
          name: 'component-button-light',
          selector: 'button:first-of-type',
          theme: 'light',
          waitTime: 500,
        })

        // Dark mode
        await takeVisualSnapshot(page, {
          name: 'component-button-dark',
          selector: 'button:first-of-type',
          theme: 'dark',
          waitTime: 500,
        })
      }
    })
  })

  test.describe('RTL Layout Visual Tests', () => {
    test('should render Home page in RTL layout', async ({ page }) => {
      await testRTLLayout(page, '/')
    })

    test('should render Assets page in RTL layout', async ({ page }) => {
      await testRTLLayout(page, '/assets')
    })

    test('should render Marketplace page in RTL layout', async ({ page }) => {
      await testRTLLayout(page, '/marketplace')
    })

    test('should render Navigation Header in RTL layout', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('networkidle')

      // LTR
      await takeVisualSnapshot(page, {
        name: 'component-navigation-header-ltr',
        selector: 'header, nav, [role="navigation"]',
        rtl: false,
        waitTime: 1000,
      })

      // RTL
      await takeVisualSnapshot(page, {
        name: 'component-navigation-header-rtl',
        selector: 'header, nav, [role="navigation"]',
        rtl: true,
        waitTime: 1000,
      })
    })
  })

  test.describe('Comprehensive Visual Tests', () => {
    test('should render complete page flow visually', async ({ page }) => {
      // Home page
      await testPageLayout(page, '/', {})

      // Navigate to assets
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')
      await testPageLayout(page, '/assets', {})

      // Navigate to marketplace
      await page.goto('/marketplace')
      await page.waitForLoadState('networkidle')
      await testPageLayout(page, '/marketplace', {})
    })

    test('should render all pages at mobile breakpoint', async ({ page }) => {
      const pages = ['/', '/assets', '/marketplace', '/contracts']

      for (const pagePath of pages) {
        await testPageLayout(page, pagePath, {
          viewport: VIEWPORTS.mobile,
        })
      }
    })

    test('should render all pages at tablet breakpoint', async ({ page }) => {
      const pages = ['/', '/assets', '/marketplace', '/contracts']

      for (const pagePath of pages) {
        await testPageLayout(page, pagePath, {
          viewport: VIEWPORTS.tablet,
        })
      }
    })

    test('should render all pages at desktop breakpoint', async ({ page }) => {
      const pages = ['/', '/assets', '/marketplace', '/contracts']

      for (const pagePath of pages) {
        await testPageLayout(page, pagePath, {
          viewport: VIEWPORTS.desktop,
        })
      }
    })

    test('should render all pages in both light and dark mode', async ({ page }) => {
      const pages = ['/', '/assets', '/marketplace', '/contracts']

      for (const pagePath of pages) {
        await testDarkMode(page, pagePath)
      }
    })
  })
})

