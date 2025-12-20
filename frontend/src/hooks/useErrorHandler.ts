/**
 * useErrorHandler Hook
 *
 * Hook for handling errors with user-friendly messages and recovery actions.
 */

import { useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import { useToast } from '@/components/feedback/Toast'
import {
  getErrorMessageConfig,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  isRecoverableError,
  type ErrorCategory,
} from '@/utils/errorMessages'
import { ApiError, NetworkError, isApiError, isNetworkError } from '@/lib/api/errors'
import { logError } from '@/services/errorLogging'

export interface ErrorHandlerOptions {
  /**
   * Show error toast notification
   */
  showToast?: boolean
  /**
   * Log error to console
   */
  logError?: boolean
  /**
   * Send error to error tracking service
   */
  trackError?: boolean
  /**
   * Custom error message override
   */
  customMessage?: string
  /**
   * Custom title override
   */
  customTitle?: string
  /**
   * Additional context for error tracking
   */
  context?: Record<string, unknown>
  /**
   * Callback when error is handled
   */
  onError?: (error: unknown, config: ReturnType<typeof getErrorMessageConfig>) => void
  /**
   * Callback for retry action
   */
  onRetry?: () => void
}

/**
 * Hook for handling errors
 */
export function useErrorHandler() {
  const toast = useToast()
  const location = useLocation()

  const handleError = useCallback(
    (error: unknown, options: ErrorHandlerOptions = {}) => {
      const {
        showToast = true,
        logError = true,
        trackError = true,
        customMessage,
        customTitle,
        context,
        onError,
        onRetry,
      } = options

      // Get error configuration
      const errorConfig = getErrorMessageConfig(error)
      const message = customMessage || errorConfig.message
      const title = customTitle || errorConfig.title

      // Log error using error logging service
      if (trackError) {
        logError(error, {
          logToConsole: logError,
          logToSentry: trackError,
          logToAnalytics: trackError,
          location,
          context: {
            ...context,
            errorCategory: errorConfig.category,
            errorSeverity: errorConfig.severity,
            ...(isApiError(error) && {
              status: error.status,
              code: error.code,
              requestId: error.requestId,
            }),
            ...(isNetworkError(error) && {
              networkError: true,
            }),
          },
          tags: {
            category: errorConfig.category,
            severity: errorConfig.severity,
          },
          level: errorConfig.severity === 'error' ? 'error' : errorConfig.severity === 'warning' ? 'warning' : 'info',
        })
      } else if (logError) {
        // Fallback to console if tracking is disabled
        console.error('[Error Handler]', {
          error,
          category: errorConfig.category,
          severity: errorConfig.severity,
          message,
          title,
          context,
          ...(isApiError(error) && {
            status: error.status,
            code: error.code,
            requestId: error.requestId,
          }),
          ...(isNetworkError(error) && {
            networkError: true,
          }),
        })
      }

      // Show toast notification
      if (showToast) {
        toast.error(message, 5000)
      }

      // Call custom error handler
      if (onError) {
        onError(error, errorConfig)
      }

      return {
        error,
        config: errorConfig,
        message,
        title,
        isRecoverable: isRecoverableError(error),
        retry: onRetry,
      }
    },
    [toast, location]
  )

  const handleApiError = useCallback(
    (error: ApiError, options?: ErrorHandlerOptions) => {
      return handleError(error, options)
    },
    [handleError]
  )

  const handleNetworkError = useCallback(
    (error: NetworkError, options?: ErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        // Network errors are usually recoverable
        onRetry: options?.onRetry,
      })
    },
    [handleError]
  )

  const handleValidationError = useCallback(
    (error: unknown, options?: ErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Validation Error',
        severity: 'warning' as const,
      })
    },
    [handleError]
  )

  const handleUnknownError = useCallback(
    (error: unknown, options?: ErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customMessage: 'An unexpected error occurred. Please try again or contact support.',
      })
    },
    [handleError]
  )

  return {
    handleError,
    handleApiError,
    handleNetworkError,
    handleValidationError,
    handleUnknownError,
    isRecoverableError,
    getErrorMessage: getUserFriendlyErrorMessage,
    getErrorTitle,
  }
}

// Extend Window interface for Sentry
declare global {
  interface Window {
    Sentry?: {
      captureException: (error: unknown, options?: Record<string, unknown>) => void
    }
  }
}

