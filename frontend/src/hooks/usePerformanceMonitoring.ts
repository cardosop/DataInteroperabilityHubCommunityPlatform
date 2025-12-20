/**
 * usePerformanceMonitoring Hook
 *
 * Hook for monitoring application performance metrics including:
 * - Web Vitals
 * - Component render times
 * - API response times
 * - Memory usage
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { getCurrentWebVitals, getMetricRating, WEB_VITALS_THRESHOLDS } from '@/services/webVitals'
import { logMessage } from '@/services/errorLogging'

export interface PerformanceMetrics {
  /**
   * Web Vitals metrics
   */
  webVitals?: {
    CLS?: number
    FCP?: number
    LCP?: number
    TTFB?: number
    INP?: number
  }
  /**
   * Component render times
   */
  renderTimes?: Record<string, number>
  /**
   * Memory usage (if available)
   */
  memory?: {
    usedJSHeapSize?: number
    totalJSHeapSize?: number
    jsHeapSizeLimit?: number
  }
  /**
   * Navigation timing
   */
  navigationTiming?: PerformanceNavigationTiming
}

export interface UsePerformanceMonitoringOptions {
  /**
   * Whether to track Web Vitals
   * @default true
   */
  trackWebVitals?: boolean
  /**
   * Whether to track component render times
   * @default true
   */
  trackRenderTimes?: boolean
  /**
   * Whether to track memory usage
   * @default false
   */
  trackMemory?: boolean
  /**
   * Callback when metrics are collected
   */
  onMetrics?: (metrics: PerformanceMetrics) => void
  /**
   * Interval for collecting metrics (in milliseconds)
   * @default 30000 (30 seconds)
   */
  collectionInterval?: number
}

export interface UsePerformanceMonitoringReturn {
  /**
   * Current performance metrics
   */
  metrics: PerformanceMetrics
  /**
   * Collect metrics manually
   */
  collectMetrics: () => Promise<void>
  /**
   * Get Web Vitals rating
   */
  getWebVitalsRating: (metricName: keyof typeof WEB_VITALS_THRESHOLDS) => 'good' | 'needs-improvement' | 'poor' | undefined
  /**
   * Check if any metric is below threshold
   */
  hasPerformanceIssues: () => boolean
}

/**
 * Hook for monitoring application performance
 *
 * @param options - Monitoring options
 * @returns Performance metrics and utilities
 *
 * @example
 * ```tsx
 * function App() {
 *   const { metrics, hasPerformanceIssues } = usePerformanceMonitoring({
 *     trackWebVitals: true,
 *     trackRenderTimes: true,
 *     onMetrics: (metrics) => {
 *       console.log('Performance metrics:', metrics)
 *     },
 *   })
 *
 *   if (hasPerformanceIssues()) {
 *     console.warn('Performance issues detected')
 *   }
 *
 *   return <div>App</div>
 * }
 * ```
 */
export function usePerformanceMonitoring(
  options: UsePerformanceMonitoringOptions = {}
): UsePerformanceMonitoringReturn {
  const {
    trackWebVitals = true,
    trackRenderTimes = true,
    trackMemory = false,
    onMetrics,
    collectionInterval = 30000,
  } = options

  const [metrics, setMetrics] = useState<PerformanceMetrics>({})
  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const renderTimesRef = useRef<Record<string, number[]>>({})

  /**
   * Collect performance metrics
   */
  const collectMetrics = useCallback(async () => {
    const collectedMetrics: PerformanceMetrics = {}

    // Collect Web Vitals
    if (trackWebVitals) {
      try {
        const webVitals = await getCurrentWebVitals()
        collectedMetrics.webVitals = webVitals
      } catch (error) {
        console.error('[Performance Monitoring] Failed to collect Web Vitals:', error)
      }
    }

    // Collect component render times
    if (trackRenderTimes) {
      const renderTimes: Record<string, number> = {}
      Object.keys(renderTimesRef.current).forEach((componentName) => {
        const times = renderTimesRef.current[componentName]
        if (times.length > 0) {
          // Calculate average render time
          const average = times.reduce((sum, time) => sum + time, 0) / times.length
          renderTimes[componentName] = average
        }
      })
      collectedMetrics.renderTimes = renderTimes
    }

    // Collect memory usage
    if (trackMemory && 'memory' in performance) {
      const memory = (performance as any).memory
      collectedMetrics.memory = {
        usedJSHeapSize: memory.usedJSHeapSize,
        totalJSHeapSize: memory.totalJSHeapSize,
        jsHeapSizeLimit: memory.jsHeapSizeLimit,
      }
    }

    // Collect navigation timing
    if ('getEntriesByType' in performance) {
      const navigationEntries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
      if (navigationEntries.length > 0) {
        collectedMetrics.navigationTiming = navigationEntries[0]
      }
    }

    setMetrics(collectedMetrics)

    // Call callback
    if (onMetrics) {
      onMetrics(collectedMetrics)
    }
  }, [trackWebVitals, trackRenderTimes, trackMemory, onMetrics])

  /**
   * Track component render time
   */
  const trackRenderTime = useCallback((componentName: string, renderTime: number) => {
    if (!trackRenderTimes) return

    if (!renderTimesRef.current[componentName]) {
      renderTimesRef.current[componentName] = []
    }

    renderTimesRef.current[componentName].push(renderTime)

    // Keep only last 100 render times per component
    if (renderTimesRef.current[componentName].length > 100) {
      renderTimesRef.current[componentName].shift()
    }
  }, [trackRenderTimes])

  /**
   * Get Web Vitals rating
   */
  const getWebVitalsRating = useCallback(
    (metricName: keyof typeof WEB_VITALS_THRESHOLDS): 'good' | 'needs-improvement' | 'poor' | undefined => {
      const value = metrics.webVitals?.[metricName]
      if (value === undefined) return undefined
      return getMetricRating(metricName, value)
    },
    [metrics.webVitals]
  )

  /**
   * Check if any metric is below threshold
   */
  const hasPerformanceIssues = useCallback((): boolean => {
    if (!metrics.webVitals) return false

    return Object.keys(WEB_VITALS_THRESHOLDS).some((metricName) => {
      const value = metrics.webVitals?.[metricName as keyof typeof metrics.webVitals]
      if (value === undefined) return false

      const rating = getMetricRating(metricName as keyof typeof WEB_VITALS_THRESHOLDS, value)
      return rating !== 'good'
    })
  }, [metrics.webVitals])

  // Set up periodic collection
  useEffect(() => {
    if (collectionInterval > 0) {
      // Initial collection
      collectMetrics()

      // Set up interval
      intervalRef.current = setInterval(() => {
        collectMetrics()
      }, collectionInterval)

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
        }
      }
    }
  }, [collectMetrics, collectionInterval])

  // Expose trackRenderTime globally for use in components
  useEffect(() => {
    if (trackRenderTimes && typeof window !== 'undefined') {
      ;(window as any).__trackComponentRenderTime = trackRenderTime
    }

    return () => {
      if (typeof window !== 'undefined') {
        delete (window as any).__trackComponentRenderTime
      }
    }
  }, [trackRenderTimes, trackRenderTime])

  return {
    metrics,
    collectMetrics,
    getWebVitalsRating,
    hasPerformanceIssues,
  }
}

