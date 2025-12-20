/**
 * Configuration Index
 *
 * Centralized configuration initialization for all dependencies.
 *
 * This module:
 * - Validates environment variables at startup
 * - Initializes all service configurations
 * - Exports type-safe configuration objects
 * - Provides helper functions for environment checks
 */

// Import environment configuration first (validates at module load)
import { config } from './env'
import { initSentry } from './sentry'
import { initAnalytics } from './analytics'
import { initWebVitals } from '@/services/webVitals'

/**
 * Initialize all application configurations
 *
 * This function should be called at application startup (in main.tsx).
 * It initializes all service configurations based on environment variables.
 */
export const initAppConfig = () => {
  // Environment validation happens automatically when this module is imported
  // The env.ts module validates all variables at module load time

  // Initialize error tracking (Sentry)
  if (config.analytics.enabled && config.analytics.sentryDsn) {
    initSentry()
  }

  // Initialize analytics (Google Analytics)
  if (config.analytics.enabled && config.analytics.gaMeasurementId) {
    // Initialize asynchronously to avoid blocking app startup
    initAnalytics().catch((error) => {
      console.error('[Analytics] Failed to initialize:', error)
    })
  }

  // Initialize Web Vitals tracking
  if (config.analytics.enabled) {
    initWebVitals()
  }

  // i18n is already initialized in its module
  // React Query, Apollo, Axios are initialized on-demand
}

// Export environment configuration
export { config, isDevelopment, isProduction, isStaging } from './env'

// Export service configurations
export * from './react-query'
export * from './apollo'
// axios config removed - using fetch instead
export * from './mui'
export * from './sentry'
export * from './analytics'
export { default as i18n } from './i18n'
