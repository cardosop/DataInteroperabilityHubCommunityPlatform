/**
 * Performance Baseline Configuration
 *
 * Defines baseline performance metrics and thresholds for:
 * - Core Web Vitals (FCP, LCP, CLS, TTFB, INP)
 * - Component render times
 * - API response times
 * - Bundle sizes
 */

import { WEB_VITALS_THRESHOLDS } from '@/services/webVitals'

/**
 * Performance baseline metrics
 *
 * These are the target metrics for the application.
 * Values are in milliseconds (except CLS which is a score).
 */
export const PERFORMANCE_BASELINE = {
  /**
   * Core Web Vitals baselines
   */
  webVitals: {
    /**
     * First Contentful Paint (FCP)
     * Target: < 1.8s (good), < 3.0s (needs improvement)
     */
    FCP: {
      target: 1800,
      acceptable: 3000,
      unit: 'ms',
      description: 'Time until first content is painted',
    },
    /**
     * Largest Contentful Paint (LCP)
     * Target: < 2.5s (good), < 4.0s (needs improvement)
     */
    LCP: {
      target: 2500,
      acceptable: 4000,
      unit: 'ms',
      description: 'Time until largest content is painted',
    },
    /**
     * Cumulative Layout Shift (CLS)
     * Target: < 0.1 (good), < 0.25 (needs improvement)
     */
    CLS: {
      target: 0.1,
      acceptable: 0.25,
      unit: 'score',
      description: 'Visual stability score',
    },
    /**
     * Time to First Byte (TTFB)
     * Target: < 800ms (good), < 1.8s (needs improvement)
     */
    TTFB: {
      target: 800,
      acceptable: 1800,
      unit: 'ms',
      description: 'Time until first byte is received',
    },
    /**
     * Interaction to Next Paint (INP)
     * Target: < 200ms (good), < 500ms (needs improvement)
     */
    INP: {
      target: 200,
      acceptable: 500,
      unit: 'ms',
      description: 'Time from interaction to next paint',
    },
  },
  /**
   * Component render time baselines
   */
  componentRender: {
    /**
     * Target render time for components
     * Should be under 16ms for 60fps
     */
    target: 16,
    /**
     * Acceptable render time
     */
    acceptable: 50,
    /**
     * Critical threshold (warn if exceeded)
     */
    critical: 100,
    unit: 'ms',
    description: 'Component render time',
  },
  /**
   * API response time baselines
   */
  apiResponse: {
    /**
     * Target API response time
     */
    target: 200,
    /**
     * Acceptable API response time
     */
    acceptable: 500,
    /**
     * Critical threshold
     */
    critical: 1000,
    unit: 'ms',
    description: 'API response time',
  },
  /**
   * Bundle size baselines
   */
  bundleSize: {
    /**
     * Target initial bundle size
     */
    target: 200 * 1024, // 200KB
    /**
     * Acceptable initial bundle size
     */
    acceptable: 500 * 1024, // 500KB
    /**
     * Critical threshold
     */
    critical: 1000 * 1024, // 1MB
    unit: 'bytes',
    description: 'Initial JavaScript bundle size',
  },
} as const

/**
 * Performance budget configuration
 *
 * Defines budgets for different performance metrics.
 * Alerts are triggered when budgets are exceeded.
 */
export const PERFORMANCE_BUDGET = {
  /**
   * Web Vitals budget
   */
  webVitals: {
    FCP: {
      budget: 3000,
      alertThreshold: 4000,
    },
    LCP: {
      budget: 4000,
      alertThreshold: 5000,
    },
    CLS: {
      budget: 0.25,
      alertThreshold: 0.3,
    },
    TTFB: {
      budget: 1800,
      alertThreshold: 2500,
    },
    INP: {
      budget: 500,
      alertThreshold: 700,
    },
  },
  /**
   * Component render time budget
   */
  componentRender: {
    budget: 50,
    alertThreshold: 100,
  },
  /**
   * API response time budget
   */
  apiResponse: {
    budget: 500,
    alertThreshold: 1000,
  },
  /**
   * Bundle size budget
   */
  bundleSize: {
    budget: 500 * 1024, // 500KB
    alertThreshold: 1000 * 1024, // 1MB
  },
} as const

/**
 * Check if a metric value exceeds the budget
 *
 * @param category - Metric category
 * @param metricName - Metric name
 * @param value - Metric value
 * @returns True if budget is exceeded
 */
export function exceedsBudget(
  category: keyof typeof PERFORMANCE_BUDGET,
  metricName: string,
  value: number
): boolean {
  const budget = PERFORMANCE_BUDGET[category]

  if (category === 'webVitals') {
    const webVitalBudget = budget[metricName as keyof typeof budget]
    return webVitalBudget ? value > webVitalBudget.budget : false
  }

  if (category === 'componentRender' || category === 'apiResponse' || category === 'bundleSize') {
    return value > (budget as any).budget
  }

  return false
}

/**
 * Check if a metric value exceeds the alert threshold
 *
 * @param category - Metric category
 * @param metricName - Metric name
 * @param value - Metric value
 * @returns True if alert threshold is exceeded
 */
export function exceedsAlertThreshold(
  category: keyof typeof PERFORMANCE_BUDGET,
  metricName: string,
  value: number
): boolean {
  const budget = PERFORMANCE_BUDGET[category]

  if (category === 'webVitals') {
    const webVitalBudget = budget[metricName as keyof typeof budget]
    return webVitalBudget ? value > webVitalBudget.alertThreshold : false
  }

  if (category === 'componentRender' || category === 'apiResponse' || category === 'bundleSize') {
    return value > (budget as any).alertThreshold
  }

  return false
}

