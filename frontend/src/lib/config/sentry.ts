/**
 * Sentry Configuration
 *
 * Comprehensive error tracking and monitoring configuration with:
 * - PII removal and data sanitization
 * - Error filtering
 * - Context capture
 * - Rate limiting
 */

import * as Sentry from '@sentry/react'
import { anonymizeObject, anonymizeError } from '@/utils/errorAnonymization'
import { globalErrorRateLimiter } from '@/utils/errorRateLimiter'
import { captureErrorContext } from '@/utils/errorContextCapture'

/**
 * Sensitive headers to remove from Sentry events
 */
const SENSITIVE_HEADERS = [
  'authorization',
  'authorization_header',
  'x-api-key',
  'x-auth-token',
  'cookie',
  'set-cookie',
  'x-csrf-token',
  'x-xsrf-token',
]

/**
 * Sensitive query parameters to remove
 */
const SENSITIVE_QUERY_PARAMS = [
  'token',
  'api_key',
  'apikey',
  'access_token',
  'refresh_token',
  'password',
  'secret',
]

/**
 * Initialize Sentry with comprehensive error filtering
 */
export const initSentry = () => {
  const dsn = import.meta.env.VITE_SENTRY_DSN

  if (!dsn) {
    console.warn('Sentry DSN not configured. Error tracking disabled.')
    return
  }

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    integrations: [
      Sentry.browserTracingIntegration({
        // Trace only same-origin requests
        tracePropagationTargets: ['localhost', /^\//],
      }),
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
        // Mask all inputs to prevent PII capture
        maskAllInputs: true,
      }),
    ],
    // Performance Monitoring
    tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    // Session Replay
    replaysSessionSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    replaysOnErrorSampleRate: 1.0,
    // Ignore specific errors
    ignoreErrors: [
      // Browser extensions
      'ResizeObserver loop limit exceeded',
      'Non-Error promise rejection captured',
      // Network errors that are handled gracefully
      'NetworkError',
      'Failed to fetch',
      // Chrome extensions
      /chrome-extension:/,
      /moz-extension:/,
    ],
    // Filter out sensitive data before sending
    beforeSend(event, hint) {
      // Rate limiting check
      const error = hint.originalException || hint.syntheticException
      if (error && !globalErrorRateLimiter.shouldReport(error)) {
        // Error is rate limited, don't send
        console.warn('[Sentry] Error rate limited, not sending to Sentry')
        return null
      }

      // Anonymize error message
      if (event.message) {
        event.message = anonymizeObject(event.message) as string
      }

      // Anonymize exception data
      if (event.exception) {
        event.exception.values = event.exception.values?.map((exception) => ({
          ...exception,
          value: exception.value
            ? anonymizeObject(exception.value) as string
            : exception.value,
          stacktrace: exception.stacktrace
            ? {
                ...exception.stacktrace,
                frames: exception.stacktrace.frames?.map((frame) => ({
                  ...frame,
                  vars: frame.vars ? anonymizeObject(frame.vars) : frame.vars,
                })),
              }
            : exception.stacktrace,
        }))
      }

      // Remove sensitive data from request
      if (event.request) {
        // Remove cookies
        if (event.request.cookies) {
          delete event.request.cookies
        }

        // Remove sensitive headers
        if (event.request.headers) {
          SENSITIVE_HEADERS.forEach((header) => {
            const lowerHeader = header.toLowerCase()
            Object.keys(event.request.headers || {}).forEach((key) => {
              if (key.toLowerCase() === lowerHeader) {
                delete event.request.headers![key]
              }
            })
          })
        }

        // Anonymize query string
        if (event.request.query_string) {
          const queryParams = new URLSearchParams(event.request.query_string)
          SENSITIVE_QUERY_PARAMS.forEach((param) => {
            if (queryParams.has(param)) {
              queryParams.set(param, '[REDACTED]')
            }
          })
          event.request.query_string = queryParams.toString()
        }

        // Anonymize URL
        if (event.request.url) {
          try {
            const url = new URL(event.request.url)
            SENSITIVE_QUERY_PARAMS.forEach((param) => {
              if (url.searchParams.has(param)) {
                url.searchParams.set(param, '[REDACTED]')
              }
            })
            event.request.url = url.toString()
          } catch {
            // Invalid URL, anonymize the whole thing
            event.request.url = anonymizeObject(event.request.url) as string
          }
        }

        // Anonymize data
        if (event.request.data) {
          event.request.data = anonymizeObject(event.request.data)
        }
      }

      // Anonymize user data
      if (event.user) {
        // Keep only non-sensitive user info
        event.user = {
          id: event.user.id ? '[REDACTED]' : undefined,
          username: event.user.username ? '[REDACTED]' : undefined,
          email: event.user.email ? '[REDACTED]' : undefined,
          ip_address: '[REDACTED]',
        }
      }

      // Anonymize tags
      if (event.tags) {
        event.tags = anonymizeObject(event.tags) as Record<string, string>
      }

      // Anonymize extra context
      if (event.extra) {
        event.extra = anonymizeObject(event.extra)
      }

      // Anonymize breadcrumbs
      if (event.breadcrumbs) {
        event.breadcrumbs = event.breadcrumbs.map((breadcrumb) => ({
          ...breadcrumb,
          message: breadcrumb.message
            ? anonymizeObject(breadcrumb.message) as string
            : breadcrumb.message,
          data: breadcrumb.data ? anonymizeObject(breadcrumb.data) : breadcrumb.data,
        }))
      }

      return event
    },
    // Set user context (anonymized)
    beforeBreadcrumb(breadcrumb) {
      // Anonymize breadcrumb data
      if (breadcrumb.data) {
        breadcrumb.data = anonymizeObject(breadcrumb.data)
      }
      if (breadcrumb.message) {
        breadcrumb.message = anonymizeObject(breadcrumb.message) as string
      }
      return breadcrumb
    },
  })
}

/**
 * Capture exception with context
 *
 * @param error - Error to capture
 * @param context - Additional context
 */
export function captureExceptionWithContext(
  error: unknown,
  context?: {
    tags?: Record<string, string>
    extra?: Record<string, any>
    level?: Sentry.SeverityLevel
    user?: {
      id?: string
      username?: string
      email?: string
    }
  }
): string | undefined {
  // Anonymize error first
  const anonymizedError = anonymizeError(error)

  // Capture error context
  const errorContext = captureErrorContext(error)

  // Set user context (anonymized)
  if (context?.user) {
    Sentry.setUser({
      id: context.user.id ? '[REDACTED]' : undefined,
      username: context.user.username ? '[REDACTED]' : undefined,
      email: context.user.email ? '[REDACTED]' : undefined,
    })
  }

  // Capture exception with context
  return Sentry.captureException(anonymizedError, {
    tags: {
      ...context?.tags,
      ...(errorContext.appState.route && { route: errorContext.appState.route }),
    },
    extra: {
      ...anonymizeObject(errorContext),
      ...anonymizeObject(context?.extra || {}),
    },
    level: context?.level || 'error',
  })
}

/**
 * Capture message with context
 *
 * @param message - Message to capture
 * @param level - Severity level
 * @param context - Additional context
 */
export function captureMessageWithContext(
  message: string,
  level: Sentry.SeverityLevel = 'info',
  context?: {
    tags?: Record<string, string>
    extra?: Record<string, any>
  }
): string {
  const errorContext = captureErrorContext(null)

  return Sentry.captureMessage(anonymizeObject(message) as string, {
    level,
    tags: {
      ...context?.tags,
      ...(errorContext.appState.route && { route: errorContext.appState.route }),
    },
    extra: {
      ...anonymizeObject(errorContext),
      ...anonymizeObject(context?.extra || {}),
    },
  })
}

/**
 * Set user context (anonymized)
 *
 * @param user - User information
 */
export function setUserContext(user: {
  id?: string
  username?: string
  email?: string
  [key: string]: any
}): void {
  Sentry.setUser({
    id: user.id ? '[REDACTED]' : undefined,
    username: user.username ? '[REDACTED]' : undefined,
    email: user.email ? '[REDACTED]' : undefined,
  })
}

/**
 * Add breadcrumb with anonymization
 *
 * @param breadcrumb - Breadcrumb data
 */
export function addBreadcrumb(breadcrumb: {
  message?: string
  category?: string
  level?: Sentry.SeverityLevel
  data?: Record<string, any>
}): void {
  Sentry.addBreadcrumb({
    ...breadcrumb,
    message: breadcrumb.message
      ? anonymizeObject(breadcrumb.message) as string
      : breadcrumb.message,
    data: breadcrumb.data ? anonymizeObject(breadcrumb.data) : breadcrumb.data,
  })
}
