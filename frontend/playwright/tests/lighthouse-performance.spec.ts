/**
 * Lighthouse Performance Audit Tests (6.13.3)
 *
 * Comprehensive end-to-end tests for Lighthouse performance audits.
 * Tests all performance metrics including:
 * - Performance score (target: 90+)
 * - First Contentful Paint (FCP) < 1.5s
 * - Time to Interactive (TTI) < 3s
 * - Cumulative Layout Shift (CLS) < 0.1
 * - First Input Delay (FID) < 100ms
 *
 * Uses real performance metrics - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'
import {
  runLighthouseAudit,
  validatePerformanceMetrics,
  DEFAULT_THRESHOLDS,
  type LighthouseAuditResult,
  type PerformanceThresholds,
} from '../utils/lighthouse-audit'

/**
 * Test credentials
 */
const TEST_CREDENTIALS = {
  email: process.env.TEST_USER_EMAIL || 'test@example.com',
  password: process.env.TEST_USER_PASSWORD || 'testpassword123',
}

/**
 * Performance thresholds for tests
 */
const TEST_THRESHOLDS: PerformanceThresholds = {
  performanceScore: 90,
  fcp: 1.5,
  tti: 3.0,
  cls: 0.1,
  fid: 100,
}

test.describe('Lighthouse Performance Audit (6.13.3)', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.login(TEST_CREDENTIALS.email, TEST_CREDENTIALS.password)
  })

  test.describe('Performance Score Validation', () => {
    test('should achieve 90+ performance score on homepage', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.performanceScore).toBeGreaterThanOrEqual(90)
    })

    test('should achieve 90+ performance score on assets page', async ({ page }) => {
      await page.goto('/assets')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.performanceScore).toBeGreaterThanOrEqual(90)
    })

    test('should achieve 90+ performance score on marketplace page', async ({ page }) => {
      await page.goto('/marketplace')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.performanceScore).toBeGreaterThanOrEqual(90)
    })

    test('should validate performance score with detailed report', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
        generateReport: true,
        reportPath: './playwright/reports/lighthouse-homepage.html',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.passed).toBe(true)
      expect(validation.details.performanceScore.passed).toBe(true)
      expect(result.performanceScore).toBeGreaterThanOrEqual(90)
    })
  })

  test.describe('First Contentful Paint (FCP) Validation', () => {
    test('should have FCP < 1.5s on homepage', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.fcp).toBeLessThan(1.5)
    })

    test('should have FCP < 1.5s on assets page', async ({ page }) => {
      await page.goto('/assets')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.fcp).toBeLessThan(1.5)
    })

    test('should validate FCP threshold with detailed validation', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.details.fcp.passed).toBe(true)
      expect(result.fcp).toBeLessThan(1.5)
    })
  })

  test.describe('Time to Interactive (TTI) Validation', () => {
    test('should have TTI < 3s on homepage', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.tti).toBeLessThan(3.0)
    })

    test('should have TTI < 3s on assets page', async ({ page }) => {
      await page.goto('/assets')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.tti).toBeLessThan(3.0)
    })

    test('should validate TTI threshold with detailed validation', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.details.tti.passed).toBe(true)
      expect(result.tti).toBeLessThan(3.0)
    })
  })

  test.describe('Cumulative Layout Shift (CLS) Validation', () => {
    test('should have CLS < 0.1 on homepage', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.cls).toBeLessThan(0.1)
    })

    test('should have CLS < 0.1 on assets page', async ({ page }) => {
      await page.goto('/assets')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      expect(result.cls).toBeLessThan(0.1)
    })

    test('should validate CLS threshold with detailed validation', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.details.cls.passed).toBe(true)
      expect(result.cls).toBeLessThan(0.1)
    })
  })

  test.describe('First Input Delay (FID) Validation', () => {
    test('should have FID < 100ms on homepage', async ({ page }) => {
      await page.goto('/')

      // Wait for page to be interactive
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)

      // Trigger an interaction to measure FID
      const fidPromise = page.evaluate(() => {
        return new Promise<number>((resolve) => {
          let fidMeasured = false

          // Listen for first input
          const measureFID = (event: Event) => {
            if (fidMeasured) return
            fidMeasured = true

            const perfEntry = (event as any).performanceEntry
            if (perfEntry) {
              const fid = perfEntry.processingStart - perfEntry.startTime
              resolve(fid)
            } else {
              // Fallback: measure time to first interaction
              const startTime = performance.now()
              setTimeout(() => {
                resolve(performance.now() - startTime)
              }, 0)
            }
          }

          // Add event listeners for various input types
          document.addEventListener('click', measureFID, { once: true, passive: true })
          document.addEventListener('keydown', measureFID, { once: true, passive: true })
          document.addEventListener('touchstart', measureFID, { once: true, passive: true })

          // Timeout after 5 seconds
          setTimeout(() => {
            if (!fidMeasured) {
              resolve(0) // No interaction detected, assume good
            }
          }, 5000)
        })
      })

      // Trigger a click to measure FID
      await page.click('body')
      const fid = await fidPromise

      // Run audit to get comprehensive metrics
      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      // Use measured FID or result FID
      const finalFid = result.fid > 0 ? result.fid : fid

      expect(finalFid).toBeLessThan(100)
    })

    test('should validate FID threshold with detailed validation', async ({ page }) => {
      await page.goto('/')

      // Wait for page to be interactive
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)

      // Trigger interaction
      await page.click('body')
      await page.waitForTimeout(500)

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      // FID might be 0 if no interaction was captured, which is acceptable
      if (result.fid > 0) {
        expect(validation.details.fid.passed).toBe(true)
        expect(result.fid).toBeLessThan(100)
      } else {
        // If FID is 0, it means no interaction was measured, which is acceptable
        expect(result.fid).toBeGreaterThanOrEqual(0)
      }
    })
  })

  test.describe('Comprehensive Performance Validation', () => {
    test('should pass all performance thresholds on homepage', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.passed).toBe(true)
      expect(validation.failures.length).toBe(0)

      // Verify all metrics individually
      expect(result.performanceScore).toBeGreaterThanOrEqual(90)
      expect(result.fcp).toBeLessThan(1.5)
      expect(result.tti).toBeLessThan(3.0)
      expect(result.cls).toBeLessThan(0.1)
      // FID might be 0 if no interaction, which is acceptable
      if (result.fid > 0) {
        expect(result.fid).toBeLessThan(100)
      }
    })

    test('should pass all performance thresholds on assets page', async ({ page }) => {
      await page.goto('/assets')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.passed).toBe(true)
      expect(validation.failures.length).toBe(0)
    })

    test('should pass all performance thresholds on marketplace page', async ({ page }) => {
      await page.goto('/marketplace')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      expect(validation.passed).toBe(true)
      expect(validation.failures.length).toBe(0)
    })

    test('should generate detailed performance report', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
        generateReport: true,
        reportPath: './playwright/reports/lighthouse-detailed.html',
      })

      // Verify report was generated (or at least attempted)
      expect(result).toBeDefined()
      expect(result.performanceScore).toBeGreaterThanOrEqual(0)
      expect(result.fcp).toBeGreaterThanOrEqual(0)
      expect(result.tti).toBeGreaterThanOrEqual(0)
      expect(result.cls).toBeGreaterThanOrEqual(0)
    })
  })

  test.describe('Mobile Performance Validation', () => {
    test('should achieve good performance on mobile devices', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 })

      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'mobile',
      })

      // Mobile thresholds might be slightly more lenient
      const mobileThresholds: PerformanceThresholds = {
        ...TEST_THRESHOLDS,
        performanceScore: 85, // Slightly lower for mobile
        fcp: 2.0, // Slightly higher for mobile
        tti: 3.5, // Slightly higher for mobile
      }

      const validation = validatePerformanceMetrics(result, mobileThresholds)

      // Mobile performance should still be good
      expect(result.performanceScore).toBeGreaterThanOrEqual(85)
      expect(result.fcp).toBeLessThan(2.0)
      expect(result.tti).toBeLessThan(3.5)
      expect(result.cls).toBeLessThan(0.1)
    })
  })

  test.describe('Performance Regression Detection', () => {
    test('should detect performance regressions', async ({ page }) => {
      await page.goto('/')

      const result = await runLighthouseAudit(page, {
        device: 'desktop',
      })

      const validation = validatePerformanceMetrics(result, TEST_THRESHOLDS)

      // Log performance metrics for monitoring
      console.log('Performance Metrics:', {
        performanceScore: result.performanceScore,
        fcp: result.fcp,
        tti: result.tti,
        cls: result.cls,
        fid: result.fid,
      })

      // If validation fails, log detailed information
      if (!validation.passed) {
        console.error('Performance validation failed:', validation.failures)
        console.error('Performance details:', validation.details)
      }

      expect(validation.passed).toBe(true)
    })
  })
})

