/**
 * Error Logging Service
 *
 * Centralized service for logging errors to multiple destinations:
 * - Sentry (error tracking)
 * - Google Analytics (analytics service)
 * - Console (development)
 */

import { captureExceptionWithContext, captureMessageWithContext } from '@/lib/config/sentry'
import { trackEvent } from '@/lib/config/analytics'
import { anonymizeError } from '@/utils/errorAnonymization'
import { captureErrorContext } from '@/utils/errorContextCapture'
import { globalErrorRateLimiter } from '@/utils/errorRateLimiter'
import type { Location } from 'react-router-dom'

export interface ErrorLoggingOptions {
  /**
   * Whether to log to Sentry
   * @default true
   */
  logToSentry?: boolean
  /**
   * Whether to log to analytics
   * @default true
   */
  logToAnalytics?: boolean
  /**
   * Whether to log to console
   * @default true in development
   */
  logToConsole?: boolean
  /**
   * React Router location (for context)
   */
  location?: Location
  /**
   * Additional tags
   */
  tags?: Record<string, string>
  /**
   * Additional context
   */
  context?: Record<string, any>
  /**
   * Error severity level
   */
  level?: 'error' | 'warning' | 'info'
  /**
   * User information (will be anonymized)
   */
  user?: {
    id?: string
    username?: string
    email?: string
  }
}

/**
 * Log error to all configured services
 *
 * @param error - Error to log
 * @param options - Logging options
 * @returns Event ID from Sentry (if logged)
 *
 * @example
 * ```tsx
 * try {
 *   await submitForm()
 * } catch (error) {
 *   logError(error, {
 *     context: { formName: 'user-registration' },
 *     tags: { feature: 'authentication' },
 *   })
 * }
 * ```
 */
export function logError(error: unknown, options: ErrorLoggingOptions = {}): string | undefined {
  const {
    logToSentry = true,
    logToAnalytics = true,
    logToConsole = import.meta.env.DEV,
    location,
    tags = {},
    context = {},
    level = 'error',
    user,
  } = options

  // Check rate limiting
  if (!globalErrorRateLimiter.shouldReport(error)) {
    if (logToConsole) {
      console.warn('[Error Logging] Error rate limited, not logging')
    }
    return undefined
  }

  // Capture error context
  const errorContext = captureErrorContext(error, {
    location,
    custom: context,
  })

  // Anonymize error
  const anonymizedError = anonymizeError(error)

  // Log to console
  if (logToConsole) {
    console.error('[Error Logging]', {
      error: anonymizedError,
      context: errorContext,
      tags,
      level,
    })
  }

  // Log to Sentry
  let sentryEventId: string | undefined
  if (logToSentry) {
    try {
      sentryEventId = captureExceptionWithContext(error, {
        tags: {
          ...tags,
          level,
          ...(errorContext.appState.route && { route: errorContext.appState.route }),
        },
        extra: {
          ...errorContext,
          ...context,
        },
        level: level as any,
        user,
      })
    } catch (sentryError) {
      console.error('[Error Logging] Failed to log to Sentry:', sentryError)
    }
  }

  // Log to analytics
  if (logToAnalytics) {
    try {
      const errorName = error instanceof Error ? error.name : 'UnknownError'
      const errorMessage = error instanceof Error ? error.message : String(error)

      trackEvent('error', 'error_occurred', {
        error_name: errorName,
        error_message: anonymizedError.message.substring(0, 100), // Limit length
        error_level: level,
        route: errorContext.appState.route,
        ...tags,
      })
    } catch (analyticsError) {
      console.error('[Error Logging] Failed to log to analytics:', analyticsError)
    }
  }

  return sentryEventId
}

/**
 * Log message to all configured services
 *
 * @param message - Message to log
 * @param options - Logging options
 * @returns Event ID from Sentry (if logged)
 */
export function logMessage(
  message: string,
  options: Omit<ErrorLoggingOptions, 'user'> = {}
): string | undefined {
  const {
    logToSentry = true,
    logToAnalytics = true,
    logToConsole = import.meta.env.DEV,
    location,
    tags = {},
    context = {},
    level = 'info',
  } = options

  // Log to console
  if (logToConsole) {
    const logMethod = level === 'error' ? console.error : level === 'warning' ? console.warn : console.log
    logMethod('[Error Logging]', message, { tags, context })
  }

  // Log to Sentry
  let sentryEventId: string | undefined
  if (logToSentry) {
    try {
      const errorContext = captureErrorContext(null, { location, custom: context })
      sentryEventId = captureMessageWithContext(message, level as any, {
        tags: {
          ...tags,
          ...(errorContext.appState.route && { route: errorContext.appState.route }),
        },
        extra: {
          ...errorContext,
          ...context,
        },
      })
    } catch (sentryError) {
      console.error('[Error Logging] Failed to log to Sentry:', sentryError)
    }
  }

  // Log to analytics
  if (logToAnalytics) {
    try {
      trackEvent('log', 'message_logged', {
        message: message.substring(0, 100), // Limit length
        level,
        ...tags,
      })
    } catch (analyticsError) {
      console.error('[Error Logging] Failed to log to analytics:', analyticsError)
    }
  }

  return sentryEventId
}

