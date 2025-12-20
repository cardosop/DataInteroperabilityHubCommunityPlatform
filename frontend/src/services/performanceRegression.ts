/**
 * Performance Regression Detection Service
 *
 * Service for detecting performance regressions by comparing current metrics
 * against baseline measurements.
 */

import { PERFORMANCE_BASELINE, PERFORMANCE_BUDGET, exceedsBudget, exceedsAlertThreshold } from '@/config/performanceBaseline'
import { logMessage } from './errorLogging'
import { trackEvent } from '@/lib/config/analytics'

export interface PerformanceMetric {
  /**
   * Metric name
   */
  name: string
  /**
   * Metric value
   */
  value: number
  /**
   * Metric category
   */
  category: 'webVitals' | 'componentRender' | 'apiResponse' | 'bundleSize'
  /**
   * Timestamp
   */
  timestamp: number
}

export interface RegressionResult {
  /**
   * Whether a regression was detected
   */
  isRegression: boolean
  /**
   * Whether alert threshold was exceeded
   */
  isAlert: boolean
  /**
   * Regression details
   */
  details: {
    metric: string
    currentValue: number
    baselineValue: number
    difference: number
    percentageChange: number
    category: string
  }
}

/**
 * Store for performance metrics history
 */
class PerformanceMetricsStore {
  private metrics: PerformanceMetric[] = []
  private readonly maxHistory = 1000

  /**
   * Add a metric
   */
  add(metric: PerformanceMetric): void {
    this.metrics.push(metric)

    // Keep only last N metrics
    if (this.metrics.length > this.maxHistory) {
      this.metrics.shift()
    }
  }

  /**
   * Get metrics for a category
   */
  getMetrics(category: string, metricName?: string): PerformanceMetric[] {
    return this.metrics.filter((m) => {
      if (m.category !== category) return false
      if (metricName && m.name !== metricName) return false
      return true
    })
  }

  /**
   * Get average value for a metric
   */
  getAverage(category: string, metricName: string, windowSize: number = 10): number {
    const recentMetrics = this.getMetrics(category, metricName).slice(-windowSize)

    if (recentMetrics.length === 0) return 0

    const sum = recentMetrics.reduce((acc, m) => acc + m.value, 0)
    return sum / recentMetrics.length
  }

  /**
   * Clear all metrics
   */
  clear(): void {
    this.metrics = []
  }
}

/**
 * Global metrics store
 */
const metricsStore = new PerformanceMetricsStore()

/**
 * Detect performance regression
 *
 * @param metric - Performance metric
 * @returns Regression result
 */
export function detectRegression(metric: PerformanceMetric): RegressionResult {
  // Store metric
  metricsStore.add(metric)

  // Get baseline value
  const baseline = PERFORMANCE_BASELINE[metric.category]

  let baselineValue: number
  if (metric.category === 'webVitals') {
    const webVitalBaseline = baseline[metric.name as keyof typeof baseline]
    baselineValue = webVitalBaseline?.target || webVitalBaseline?.acceptable || 0
  } else {
    baselineValue = (baseline as any).target || (baseline as any).acceptable || 0
  }

  // Calculate difference
  const difference = metric.value - baselineValue
  const percentageChange = baselineValue > 0 ? (difference / baselineValue) * 100 : 0

  // Check if exceeds budget
  const exceeds = exceedsBudget(metric.category, metric.name, metric.value)
  const isAlert = exceedsAlertThreshold(metric.category, metric.name, metric.value)

  // Consider it a regression if:
  // 1. Value exceeds budget, OR
  // 2. Value is 20% worse than baseline
  const isRegression = exceeds || percentageChange > 20

  const result: RegressionResult = {
    isRegression,
    isAlert,
    details: {
      metric: metric.name,
      currentValue: metric.value,
      baselineValue,
      difference,
      percentageChange,
      category: metric.category,
    },
  }

  // Log regression
  if (isRegression) {
    logMessage(
      `Performance regression detected: ${metric.name} = ${metric.value.toFixed(2)} (baseline: ${baselineValue.toFixed(2)}, change: ${percentageChange.toFixed(1)}%)`,
      {
        level: isAlert ? 'error' : 'warning',
        context: result.details,
        tags: {
          performance: 'true',
          regression: 'true',
          category: metric.category,
          metric: metric.name,
        },
      }
    )

    // Track in analytics
    trackEvent('performance_regression', metric.name, undefined, metric.value, {
      baseline: baselineValue,
      difference,
      percentage_change: percentageChange,
      category: metric.category,
    })
  }

  return result
}

/**
 * Get performance metrics history
 *
 * @param category - Metric category
 * @param metricName - Metric name (optional)
 * @returns Array of metrics
 */
export function getMetricsHistory(
  category: string,
  metricName?: string
): PerformanceMetric[] {
  return metricsStore.getMetrics(category, metricName)
}

/**
 * Get average metric value
 *
 * @param category - Metric category
 * @param metricName - Metric name
 * @param windowSize - Number of recent metrics to average
 * @returns Average value
 */
export function getAverageMetric(
  category: string,
  metricName: string,
  windowSize: number = 10
): number {
  return metricsStore.getAverage(category, metricName, windowSize)
}

/**
 * Clear metrics history
 */
export function clearMetricsHistory(): void {
  metricsStore.clear()
}

