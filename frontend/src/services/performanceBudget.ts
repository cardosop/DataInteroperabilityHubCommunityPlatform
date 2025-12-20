/**
 * Performance Budget Alerts Service
 *
 * Service for monitoring performance budgets and triggering alerts
 * when budgets are exceeded.
 */

import { PERFORMANCE_BUDGET, exceedsBudget, exceedsAlertThreshold } from '@/config/performanceBaseline'
import { logMessage } from './errorLogging'
import { trackEvent } from '@/lib/config/analytics'
import { detectRegression } from './performanceRegression'

export interface BudgetAlert {
  /**
   * Alert ID
   */
  id: string
  /**
   * Metric category
   */
  category: 'webVitals' | 'componentRender' | 'apiResponse' | 'bundleSize'
  /**
   * Metric name
   */
  metric: string
  /**
   * Current value
   */
  value: number
  /**
   * Budget threshold
   */
  budget: number
  /**
   * Alert threshold
   */
  alertThreshold: number
  /**
   * Timestamp
   */
  timestamp: number
  /**
   * Severity
   */
  severity: 'warning' | 'error'
}

/**
 * Store for active alerts
 */
class BudgetAlertsStore {
  private alerts: Map<string, BudgetAlert> = new Map()
  private readonly alertCooldown = 60000 // 1 minute

  /**
   * Check if alert should be triggered
   */
  shouldTriggerAlert(alertId: string): boolean {
    const existingAlert = this.alerts.get(alertId)

    if (!existingAlert) {
      return true
    }

    // Check cooldown
    const timeSinceLastAlert = Date.now() - existingAlert.timestamp
    return timeSinceLastAlert > this.alertCooldown
  }

  /**
   * Add or update alert
   */
  addAlert(alert: BudgetAlert): void {
    this.alerts.set(alert.id, alert)
  }

  /**
   * Get all active alerts
   */
  getAlerts(): BudgetAlert[] {
    return Array.from(this.alerts.values())
  }

  /**
   * Clear alert
   */
  clearAlert(alertId: string): void {
    this.alerts.delete(alertId)
  }

  /**
   * Clear all alerts
   */
  clearAll(): void {
    this.alerts.clear()
  }
}

/**
 * Global alerts store
 */
const alertsStore = new BudgetAlertsStore()

/**
 * Check performance budget and trigger alerts
 *
 * @param category - Metric category
 * @param metricName - Metric name
 * @param value - Metric value
 * @returns Alert if budget exceeded, null otherwise
 */
export function checkBudget(
  category: 'webVitals' | 'componentRender' | 'apiResponse' | 'bundleSize',
  metricName: string,
  value: number
): BudgetAlert | null {
  const alertId = `${category}:${metricName}`

  // Check if budget is exceeded
  if (!exceedsBudget(category, metricName, value)) {
    // Clear alert if value is back within budget
    alertsStore.clearAlert(alertId)
    return null
  }

  // Check if alert should be triggered (cooldown)
  if (!alertsStore.shouldTriggerAlert(alertId)) {
    return alertsStore.getAlerts().find((a) => a.id === alertId) || null
  }

  // Get budget configuration
  const budget = PERFORMANCE_BUDGET[category]
  let budgetValue: number
  let alertThresholdValue: number

  if (category === 'webVitals') {
    const webVitalBudget = budget[metricName as keyof typeof budget]
    if (!webVitalBudget) return null
    budgetValue = webVitalBudget.budget
    alertThresholdValue = webVitalBudget.alertThreshold
  } else {
    budgetValue = (budget as any).budget
    alertThresholdValue = (budget as any).alertThreshold
  }

  // Determine severity
  const severity = exceedsAlertThreshold(category, metricName, value) ? 'error' : 'warning'

  // Create alert
  const alert: BudgetAlert = {
    id: alertId,
    category,
    metric: metricName,
    value,
    budget: budgetValue,
    alertThreshold: alertThresholdValue,
    timestamp: Date.now(),
    severity,
  }

  // Store alert
  alertsStore.addAlert(alert)

  // Log alert
  logMessage(
    `Performance budget exceeded: ${metricName} = ${value.toFixed(2)} (budget: ${budgetValue.toFixed(2)}, threshold: ${alertThresholdValue.toFixed(2)})`,
    {
      level: severity,
      context: {
        category,
        metric: metricName,
        value,
        budget: budgetValue,
        alertThreshold: alertThresholdValue,
      },
      tags: {
        performance: 'true',
        budget_alert: 'true',
        category,
        metric: metricName,
        severity,
      },
    }
  )

  // Track in analytics
  trackEvent('performance_budget_exceeded', metricName, undefined, value, {
    budget: budgetValue,
    alert_threshold: alertThresholdValue,
    category,
    severity,
  })

  // Detect regression
  detectRegression({
    name: metricName,
    value,
    category,
    timestamp: Date.now(),
  })

  return alert
}

/**
 * Get all active budget alerts
 *
 * @returns Array of active alerts
 */
export function getActiveAlerts(): BudgetAlert[] {
  return alertsStore.getAlerts()
}

/**
 * Clear all budget alerts
 */
export function clearAlerts(): void {
  alertsStore.clearAll()
}

/**
 * Monitor Web Vitals and check budgets
 *
 * @param metricName - Web Vital metric name
 * @param value - Metric value
 */
export function monitorWebVital(metricName: string, value: number): void {
  checkBudget('webVitals', metricName, value)
}

/**
 * Monitor component render time and check budget
 *
 * @param componentName - Component name
 * @param renderTime - Render time in milliseconds
 */
export function monitorComponentRender(componentName: string, renderTime: number): void {
  checkBudget('componentRender', componentName, renderTime)
}

/**
 * Monitor API response time and check budget
 *
 * @param endpoint - API endpoint
 * @param responseTime - Response time in milliseconds
 */
export function monitorAPIResponse(endpoint: string, responseTime: number): void {
  checkBudget('apiResponse', endpoint, responseTime)
}

