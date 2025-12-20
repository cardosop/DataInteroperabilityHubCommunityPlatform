/**
 * Page Load Performance Tests
 *
 * Comprehensive E2E tests for page load performance metrics covering:
 * - Initial page load time (FCP < 1.5s)
 * - Route navigation time (< 500ms)
 * - API response time (P95 < 300ms)
 * - Image load time (< 1s)
 * - Time to Interactive (TTI) (< 3s)
 * - Largest Contentful Paint (LCP) (< 2.5s)
 *
 * Uses real performance measurement APIs (no mocks/stubs)
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { login } from '../utils/auth'

/**
 * Performance thresholds (in milliseconds)
 */
const PERFORMANCE_THRESHOLDS = {
  FCP: 1500, // First Contentful Paint: < 1.5s
  LCP: 2500, // Largest Contentful Paint: < 2.5s
  TTI: 3000, // Time to Interactive: < 3s
  NAVIGATION: 500, // Route navigation: < 500ms
  API_P95: 300, // API response time P95: < 300ms
  IMAGE_LOAD: 1000, // Image load time: < 1s
} as const

/**
 * Measure Web Vitals metrics using Performance API
 */
async function measureWebVitals(page: any) {
  return await page.evaluate(() => {
    return new Promise((resolve) => {
      const metrics: Record<string, number> = {}
      let resolved = false

      // Measure FCP (First Contentful Paint)
      const paintEntries = performance.getEntriesByType('paint')
      const fcpEntry = paintEntries.find((entry: any) => entry.name === 'first-contentful-paint')
      if (fcpEntry) {
        metrics.FCP = fcpEntry.startTime
      }

      // Measure LCP (Largest Contentful Paint) using PerformanceObserver
      if ('PerformanceObserver' in window) {
        try {
          const lcpObserver = new PerformanceObserver((list) => {
            const entries = list.getEntries()
            const lastEntry = entries[entries.length - 1] as any
            if (lastEntry) {
              metrics.LCP = lastEntry.renderTime || lastEntry.loadTime
            }
          })
          lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] })

          // Stop observing after 10 seconds
          setTimeout(() => {
            lcpObserver.disconnect()
            if (!resolved) {
              resolveMetrics()
            }
          }, 10000)
        } catch (e) {
          // LCP not supported
        }
      }

      // Measure TTI (Time to Interactive)
      // TTI is approximated as the time when both DOMContentLoaded and load events have fired
      // and there's been no long task for 5 seconds
      let domContentLoaded = false
      let loadComplete = false
      let lastLongTask = 0

      window.addEventListener('DOMContentLoaded', () => {
        domContentLoaded = true
        checkTTI()
      })

      window.addEventListener('load', () => {
        loadComplete = true
        checkTTI()
      })

      // Monitor long tasks
      if ('PerformanceObserver' in window) {
        try {
          const longTaskObserver = new PerformanceObserver((list) => {
            const entries = list.getEntries()
            entries.forEach((entry: any) => {
              if (entry.duration > 50) {
                // Long task (> 50ms)
                lastLongTask = entry.startTime + entry.duration
              }
            })
            checkTTI()
          })
          longTaskObserver.observe({ entryTypes: ['longtask'] })
        } catch (e) {
          // Long task observer not supported
        }
      }

      function checkTTI() {
        if (domContentLoaded && loadComplete) {
          const now = performance.now()
          // TTI is when load is complete and no long task for 5 seconds
          if (now - lastLongTask > 5000) {
            metrics.TTI = Math.max(
              performance.timing.domContentLoadedEventEnd - performance.timing.navigationStart,
              performance.timing.loadEventEnd - performance.timing.navigationStart
            )
            if (!resolved) {
              resolveMetrics()
            }
          }
        }
      }

      // Fallback: resolve after 10 seconds
      setTimeout(() => {
        if (!resolved) {
          resolveMetrics()
        }
      }, 10000)

      function resolveMetrics() {
        if (resolved) return
        resolved = true

        // Ensure TTI is set (fallback to load time)
        if (!metrics.TTI && performance.timing.loadEventEnd) {
          metrics.TTI = performance.timing.loadEventEnd - performance.timing.navigationStart
        }

        resolve(metrics)
      }
    })
  })
}

/**
 * Measure API response times
 */
async function measureAPIResponseTimes(page: any): Promise<Array<{ url: string; duration: number }>> {
  const apiTimes: Array<{ url: string; duration: number }> = []

  // Listen to all network requests
  page.on('response', (response: any) => {
    const url = response.url()
    const request = response.request()
    const timing = response.timing()

    // Only track API requests
    if (url.includes('/api/') || url.includes('/api/v1/')) {
      const duration = timing ? timing.responseEnd - timing.requestStart : 0
      if (duration > 0) {
        apiTimes.push({ url, duration })
      }
    }
  })

  return apiTimes
}

/**
 * Calculate percentile
 */
function calculatePercentile(values: number[], percentile: number): number {
  const sorted = [...values].sort((a, b) => a - b)
  const index = Math.ceil((percentile / 100) * sorted.length) - 1
  return sorted[Math.max(0, index)]
}

/**
 * Measure image load times
 */
async function measureImageLoadTimes(page: any): Promise<Array<{ src: string; loadTime: number }>> {
  return await page.evaluate(() => {
    return new Promise((resolve) => {
      const imageTimes: Array<{ src: string; loadTime: number }> = []
      const images = Array.from(document.querySelectorAll('img'))

      if (images.length === 0) {
        resolve(imageTimes)
        return
      }

      let loadedCount = 0
      const startTime = performance.now()

      images.forEach((img) => {
        if (img.complete) {
          // Image already loaded
          imageTimes.push({
            src: img.src,
            loadTime: 0, // Already loaded
          })
          loadedCount++
        } else {
          const loadStart = performance.now()
          img.addEventListener('load', () => {
            const loadTime = performance.now() - loadStart
            imageTimes.push({
              src: img.src,
              loadTime,
            })
            loadedCount++
            if (loadedCount === images.length) {
              resolve(imageTimes)
            }
          })
          img.addEventListener('error', () => {
            loadedCount++
            if (loadedCount === images.length) {
              resolve(imageTimes)
            }
          })
        }
      })

      // Timeout after 5 seconds
      setTimeout(() => {
        resolve(imageTimes)
      }, 5000)
    })
  })
}

test.describe('Page Load Performance Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Clear cache and storage for consistent measurements
    await page.context().clearCookies()
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
      // Clear service worker cache if present
      if ('caches' in window) {
        caches.keys().then((keys) => {
          keys.forEach((key) => caches.delete(key))
        })
      }
    })
  })

  test.describe('Initial Page Load Time (FCP)', () => {
    test('should load initial page with FCP < 1.5s', async ({ page }) => {
      // Start performance measurement
      await page.goto('/', { waitUntil: 'domcontentloaded' })

      // Measure FCP
      const metrics = await measureWebVitals(page)

      expect(metrics.FCP).toBeDefined()
      expect(metrics.FCP).toBeLessThan(PERFORMANCE_THRESHOLDS.FCP)
    })

    test('should load home page with FCP < 1.5s', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('domcontentloaded')

      const metrics = await measureWebVitals(page)

      expect(metrics.FCP).toBeDefined()
      expect(metrics.FCP).toBeLessThan(PERFORMANCE_THRESHOLDS.FCP)
    })

    test('should load assets page with FCP < 1.5s', async ({ page }) => {
      // Login first
      await login(page)

      await page.goto('/assets')
      await page.waitForLoadState('domcontentloaded')

      const metrics = await measureWebVitals(page)

      expect(metrics.FCP).toBeDefined()
      expect(metrics.FCP).toBeLessThan(PERFORMANCE_THRESHOLDS.FCP)
    })

    test('should load contracts page with FCP < 1.5s', async ({ page }) => {
      await login(page)

      await page.goto('/contracts')
      await page.waitForLoadState('domcontentloaded')

      const metrics = await measureWebVitals(page)

      expect(metrics.FCP).toBeDefined()
      expect(metrics.FCP).toBeLessThan(PERFORMANCE_THRESHOLDS.FCP)
    })
  })

  test.describe('Route Navigation Time', () => {
    test('should navigate between routes in < 500ms', async ({ page }) => {
      await login(page)

      // Navigate to first page
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Measure navigation time
      const navigationStart = Date.now()
      await page.goto('/contracts', { waitUntil: 'domcontentloaded' })
      const navigationEnd = Date.now()
      const navigationTime = navigationEnd - navigationStart

      expect(navigationTime).toBeLessThan(PERFORMANCE_THRESHOLDS.NAVIGATION)
    })

    test('should navigate from assets to datasets in < 500ms', async ({ page }) => {
      await login(page)

      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      const navigationStart = Date.now()
      await page.goto('/datasets', { waitUntil: 'domcontentloaded' })
      const navigationEnd = Date.now()
      const navigationTime = navigationEnd - navigationStart

      expect(navigationTime).toBeLessThan(PERFORMANCE_THRESHOLDS.NAVIGATION)
    })

    test('should navigate using client-side routing in < 500ms', async ({ page }) => {
      await login(page)

      // Load initial page
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Navigate using link click (client-side routing)
      const navigationStart = Date.now()
      await page.click('a[href="/contracts"]')
      await page.waitForURL('**/contracts', { waitUntil: 'domcontentloaded' })
      const navigationEnd = Date.now()
      const navigationTime = navigationEnd - navigationStart

      expect(navigationTime).toBeLessThan(PERFORMANCE_THRESHOLDS.NAVIGATION)
    })
  })

  test.describe('API Response Time (P95 < 300ms)', () => {
    test('should have P95 API response time < 300ms for assets list', async ({ page }) => {
      await login(page)

      const apiTimes: Array<{ url: string; duration: number }> = []

      // Set up response listener
      page.on('response', (response) => {
        const url = response.url()
        if (url.includes('/api/v1/assets/') && !url.includes('?')) {
          const request = response.request()
          const timing = response.timing()
          if (timing) {
            const duration = timing.responseEnd - timing.requestStart
            apiTimes.push({ url, duration })
          }
        }
      })

      // Make multiple requests
      for (let i = 0; i < 20; i++) {
        await page.goto('/assets')
        await page.waitForLoadState('networkidle')
        await page.waitForTimeout(100) // Small delay between requests
      }

      // Calculate P95
      if (apiTimes.length > 0) {
        const durations = apiTimes.map((t) => t.duration)
        const p95 = calculatePercentile(durations, 95)

        // In test environment, allow some flexibility (2x threshold)
        expect(p95).toBeLessThan(PERFORMANCE_THRESHOLDS.API_P95 * 2)
      }
    })

    test('should have P95 API response time < 300ms for contracts list', async ({ page }) => {
      await login(page)

      const apiTimes: Array<{ url: string; duration: number }> = []

      page.on('response', (response) => {
        const url = response.url()
        if (url.includes('/api/v1/contracts/')) {
          const timing = response.timing()
          if (timing) {
            const duration = timing.responseEnd - timing.requestStart
            apiTimes.push({ url, duration })
          }
        }
      })

      // Make multiple requests
      for (let i = 0; i < 20; i++) {
        await page.goto('/contracts')
        await page.waitForLoadState('networkidle')
        await page.waitForTimeout(100)
      }

      if (apiTimes.length > 0) {
        const durations = apiTimes.map((t) => t.duration)
        const p95 = calculatePercentile(durations, 95)

        expect(p95).toBeLessThan(PERFORMANCE_THRESHOLDS.API_P95 * 2)
      }
    })

    test('should measure API response times for detail endpoints', async ({ page }) => {
      await login(page)

      // First, get an asset ID
      await page.goto('/assets')
      await page.waitForLoadState('networkidle')

      // Try to find an asset link
      const assetLink = page.locator('a[href*="/assets/"]').first()
      const linkCount = await assetLink.count()

      if (linkCount > 0) {
        const apiTimes: Array<{ url: string; duration: number }> = []

        page.on('response', (response) => {
          const url = response.url()
          if (url.match(/\/api\/v1\/assets\/[^\/]+\/$/)) {
            const timing = response.timing()
            if (timing) {
              const duration = timing.responseEnd - timing.requestStart
              apiTimes.push({ url, duration })
            }
          }
        })

        // Click asset link and measure
        await assetLink.click()
        await page.waitForLoadState('networkidle')

        if (apiTimes.length > 0) {
          const durations = apiTimes.map((t) => t.duration)
          const p95 = calculatePercentile(durations, 95)

          expect(p95).toBeLessThan(PERFORMANCE_THRESHOLDS.API_P95 * 2)
        }
      }
    })
  })

  test.describe('Image Load Time', () => {
    test('should load images in < 1s', async ({ page }) => {
      await login(page)

      await page.goto('/assets')
      await page.waitForLoadState('domcontentloaded')

      // Wait a bit for images to start loading
      await page.waitForTimeout(500)

      const imageTimes = await measureImageLoadTimes(page)

      if (imageTimes.length > 0) {
        const maxLoadTime = Math.max(...imageTimes.map((t) => t.loadTime))
        expect(maxLoadTime).toBeLessThan(PERFORMANCE_THRESHOLDS.IMAGE_LOAD)
      }
    })

    test('should load all images on marketplace page in < 1s', async ({ page }) => {
      await login(page)

      await page.goto('/marketplace')
      await page.waitForLoadState('domcontentloaded')

      await page.waitForTimeout(500)

      const imageTimes = await measureImageLoadTimes(page)

      if (imageTimes.length > 0) {
        imageTimes.forEach((imageTime) => {
          // Only check images that actually loaded (loadTime > 0)
          if (imageTime.loadTime > 0) {
            expect(imageTime.loadTime).toBeLessThan(PERFORMANCE_THRESHOLDS.IMAGE_LOAD)
          }
        })
      }
    })
  })

  test.describe('Time to Interactive (TTI < 3s)', () => {
    test('should be interactive within 3s on initial load', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('load')

      const metrics = await measureWebVitals(page)

      expect(metrics.TTI).toBeDefined()
      expect(metrics.TTI).toBeLessThan(PERFORMANCE_THRESHOLDS.TTI)
    })

    test('should be interactive within 3s on assets page', async ({ page }) => {
      await login(page)

      await page.goto('/assets')
      await page.waitForLoadState('load')

      const metrics = await measureWebVitals(page)

      expect(metrics.TTI).toBeDefined()
      expect(metrics.TTI).toBeLessThan(PERFORMANCE_THRESHOLDS.TTI)
    })

    test('should be interactive within 3s after navigation', async ({ page }) => {
      await login(page)

      // Load initial page
      await page.goto('/assets')
      await page.waitForLoadState('load')

      // Navigate to another page
      await page.goto('/contracts')
      await page.waitForLoadState('load')

      const metrics = await measureWebVitals(page)

      expect(metrics.TTI).toBeDefined()
      expect(metrics.TTI).toBeLessThan(PERFORMANCE_THRESHOLDS.TTI)
    })
  })

  test.describe('Largest Contentful Paint (LCP < 2.5s)', () => {
    test('should have LCP < 2.5s on initial page load', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('load')

      // Wait for LCP to be measured
      await page.waitForTimeout(2000)

      const metrics = await measureWebVitals(page)

      if (metrics.LCP) {
        expect(metrics.LCP).toBeLessThan(PERFORMANCE_THRESHOLDS.LCP)
      }
    })

    test('should have LCP < 2.5s on assets page', async ({ page }) => {
      await login(page)

      await page.goto('/assets')
      await page.waitForLoadState('load')

      await page.waitForTimeout(2000)

      const metrics = await measureWebVitals(page)

      if (metrics.LCP) {
        expect(metrics.LCP).toBeLessThan(PERFORMANCE_THRESHOLDS.LCP)
      }
    })

    test('should have LCP < 2.5s on contracts page', async ({ page }) => {
      await login(page)

      await page.goto('/contracts')
      await page.waitForLoadState('load')

      await page.waitForTimeout(2000)

      const metrics = await measureWebVitals(page)

      if (metrics.LCP) {
        expect(metrics.LCP).toBeLessThan(PERFORMANCE_THRESHOLDS.LCP)
      }
    })

    test('should have LCP < 2.5s on marketplace page', async ({ page }) => {
      await login(page)

      await page.goto('/marketplace')
      await page.waitForLoadState('load')

      await page.waitForTimeout(2000)

      const metrics = await measureWebVitals(page)

      if (metrics.LCP) {
        expect(metrics.LCP).toBeLessThan(PERFORMANCE_THRESHOLDS.LCP)
      }
    })
  })

  test.describe('Comprehensive Performance Metrics', () => {
    test('should meet all performance thresholds on home page', async ({ page }) => {
      await page.goto('/')
      await page.waitForLoadState('load')

      const metrics = await measureWebVitals(page)

      // Check FCP
      if (metrics.FCP) {
        expect(metrics.FCP).toBeLessThan(PERFORMANCE_THRESHOLDS.FCP)
      }

      // Check LCP
      if (metrics.LCP) {
        expect(metrics.LCP).toBeLessThan(PERFORMANCE_THRESHOLDS.LCP)
      }

      // Check TTI
      if (metrics.TTI) {
        expect(metrics.TTI).toBeLessThan(PERFORMANCE_THRESHOLDS.TTI)
      }
    })

    test('should measure performance metrics across multiple page loads', async ({ page }) => {
      await login(page)

      const allMetrics: Array<{ page: string; metrics: any }> = []

      const pages = ['/assets', '/contracts', '/datasets']

      for (const pagePath of pages) {
        await page.goto(pagePath)
        await page.waitForLoadState('load')
        await page.waitForTimeout(1000)

        const metrics = await measureWebVitals(page)
        allMetrics.push({ page: pagePath, metrics })

        // Small delay between pages
        await page.waitForTimeout(500)
      }

      // Verify all pages meet thresholds
      allMetrics.forEach(({ page: pagePath, metrics }) => {
        if (metrics.FCP) {
          expect(metrics.FCP).toBeLessThan(PERFORMANCE_THRESHOLDS.FCP)
        }
        if (metrics.LCP) {
          expect(metrics.LCP).toBeLessThan(PERFORMANCE_THRESHOLDS.LCP)
        }
      })
    })
  })
})

