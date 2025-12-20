/**
 * Web Vitals Tracking Service
 *
 * Service for tracking Core Web Vitals and other performance metrics.
 * Integrates with Google Analytics and custom analytics endpoints.
 */

import { trackEvent } from '@/lib/config/analytics'
// Note: web-vitals is excluded from optimizeDeps to avoid CommonJS interop issues
// We use dynamic imports instead
import { logMessage } from './errorLogging'

export interface WebVitalMetric {
  /**
   * Metric name (CLS, FCP, LCP, TTFB, INP)
   */
  name: 'CLS' | 'FCP' | 'LCP' | 'TTFB' | 'INP'
  /**
   * Metric value
   */
  value: number
  /**
   * Metric ID (for deduplication)
   */
  id: string
  /**
   * Navigation type
   */
  navigationType?: 'navigate' | 'reload' | 'back_forward' | 'prerender'
  /**
   * Rating (good, needs-improvement, poor)
   */
  rating?: 'good' | 'needs-improvement' | 'poor'
}

/**
 * Web Vitals thresholds (in milliseconds or score)
 */
export const WEB_VITALS_THRESHOLDS = {
  CLS: {
    good: 0.1,
    needsImprovement: 0.25,
  },
  FCP: {
    good: 1800,
    needsImprovement: 3000,
  },
  LCP: {
    good: 2500,
    needsImprovement: 4000,
  },
  TTFB: {
    good: 800,
    needsImprovement: 1800,
  },
  INP: {
    good: 200,
    needsImprovement: 500,
  },
} as const

/**
 * Get rating for a metric value
 */
export function getMetricRating(
  metricName: keyof typeof WEB_VITALS_THRESHOLDS,
  value: number
): 'good' | 'needs-improvement' | 'poor' {
  const thresholds = WEB_VITALS_THRESHOLDS[metricName]

  if (value <= thresholds.good) {
    return 'good'
  } else if (value <= thresholds.needsImprovement) {
    return 'needs-improvement'
  } else {
    return 'poor'
  }
}

/**
 * Send Web Vital metric to analytics
 */
function sendToAnalytics(metric: WebVitalMetric) {
  const rating = metric.rating || getMetricRating(metric.name, metric.value)

  // Send to Google Analytics
  try {
    // trackEvent is async, but we don't need to await it
    trackEvent('web_vital', metric.name.toLowerCase(), metric.id, Math.round(metric.value), {
      metric_id: metric.id,
      rating,
      navigation_type: metric.navigationType || 'unknown',
    }).catch((error) => {
      console.error('[Web Vitals] Failed to send to Google Analytics:', error)
    })
  } catch (error) {
    console.error('[Web Vitals] Failed to send to Google Analytics:', error)
  }

  // Log to console in development
  if (import.meta.env.DEV) {
    console.log(`[Web Vitals] ${metric.name}:`, {
      value: metric.value,
      rating,
      id: metric.id,
    })
  }

  // Send to error logging service for monitoring
  if (rating === 'poor') {
    logMessage(`Poor Web Vital: ${metric.name} = ${Math.round(metric.value)}`, {
      level: 'warning',
      context: {
        metric: metric.name,
        value: metric.value,
        rating,
        id: metric.id,
      },
      tags: {
        performance: 'true',
        web_vital: metric.name,
        rating,
      },
    })
  }
}

/**
 * Initialize Web Vitals tracking
 *
 * Tracks Core Web Vitals:
 * - CLS (Cumulative Layout Shift)
 * - FCP (First Contentful Paint)
 * - LCP (Largest Contentful Paint)
 * - TTFB (Time to First Byte)
 * - INP (Interaction to Next Paint)
 */
export function initWebVitals() {
  if (typeof window === 'undefined') {
    return
  }

  // Use dynamic import to avoid CommonJS/ESM interop issues
  import('web-vitals').then(({ onCLS, onFCP, onLCP, onTTFB, onINP }) => {
    // Track CLS (Cumulative Layout Shift)
    onCLS(sendToAnalytics)

    // Track FCP (First Contentful Paint)
    onFCP(sendToAnalytics)

    // Track LCP (Largest Contentful Paint)
    onLCP(sendToAnalytics)

    // Track TTFB (Time to First Byte)
    onTTFB(sendToAnalytics)

    // Track INP (Interaction to Next Paint) - replaces FID
    onINP(sendToAnalytics)
  }).catch((error) => {
    console.error('[Web Vitals] Failed to load web-vitals:', error)
  })
}

/**
 * Get current Web Vitals metrics
 *
 * @returns Promise resolving to current metrics
 */
export async function getCurrentWebVitals(): Promise<Partial<Record<string, number>>> {
  return new Promise(resolve => {
    const metrics: Partial<Record<string, number>> = {}
    let count = 0
    const expectedMetrics = 5 // CLS, FCP, LCP, TTFB, INP

    const handleMetric = (metric: WebVitalMetric) => {
      metrics[metric.name] = metric.value
      count++

      if (count >= expectedMetrics) {
        resolve(metrics)
      }
    }

    // Set timeout to resolve even if not all metrics are available
    setTimeout(() => {
      resolve(metrics)
    }, 5000)

    // Use dynamic import to avoid CommonJS/ESM interop issues
    import('web-vitals').then(({ onCLS, onFCP, onLCP, onTTFB, onINP }) => {
      onCLS(handleMetric)
      onFCP(handleMetric)
      onLCP(handleMetric)
      onTTFB(handleMetric)
      onINP(handleMetric)
    }).catch((error) => {
      console.error('[Web Vitals] Failed to load web-vitals:', error)
      resolve(metrics) // Resolve with whatever metrics we have
    })
  })
}
