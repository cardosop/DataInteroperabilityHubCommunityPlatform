/**
 * useApiErrorHandler Hook
 *
 * Comprehensive API error handling hook with:
 * - Error code mapping (UNAUTHORIZED, FORBIDDEN, NOT_FOUND, VALIDATION_ERROR, RATE_LIMIT_EXCEEDED, SERVER_ERROR, NETWORK_ERROR)
 * - User-friendly error messages
 * - Automatic retry for transient errors (5xx, network errors)
 * - Manual retry with max retry limit
 * - Error context preservation
 * - Error toast notifications
 * - Error tracking
 */

import { useCallback, useRef, useState } from 'react'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import {
  getErrorMessageConfig,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  isRecoverableError,
  type ErrorCategory,
} from '@/utils/errorMessages'
import {
  ApiException,
  ValidationException,
  AuthenticationException,
  AuthorizationException,
  NotFoundException,
  RateLimitException,
  ServerException,
  isApiException,
  parseApiException,
} from '@/lib/api/exceptions'
import { FetchError } from '@/lib/api/fetch'
import { NetworkError, isNetworkError } from '@/lib/api/errors'

/**
 * Error code enum
 */
export enum ErrorCode {
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  SERVER_ERROR = 'SERVER_ERROR',
  NETWORK_ERROR = 'NETWORK_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR',
}

/**
 * Retry configuration
 */
export interface RetryConfig {
  /**
   * Maximum number of retry attempts
   */
  maxRetries: number
  /**
   * Initial delay in milliseconds
   */
  initialDelay: number
  /**
   * Maximum delay in milliseconds
   */
  maxDelay: number
  /**
   * Exponential backoff multiplier
   */
  backoffMultiplier: number
  /**
   * Retry condition function
   */
  shouldRetry: (error: unknown, attempt: number) => boolean
}

/**
 * Default retry configuration
 */
const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffMultiplier: 2,
  shouldRetry: (error: unknown, attempt: number) => {
    // Retry on network errors
    if (isNetworkError(error)) {
      return true
    }

    // Retry on server errors (5xx)
    if (isApiException(error)) {
      return error.isServerError() && attempt < 3
    }

    // Retry on rate limit (with backoff)
    if (isApiException(error) && error.isRateLimitError()) {
      return attempt < 2
    }

    return false
  },
}

/**
 * Error handler options
 */
export interface ApiErrorHandlerOptions {
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
   * Retry configuration
   */
  retryConfig?: Partial<RetryConfig>
  /**
   * Enable automatic retry
   */
  autoRetry?: boolean
  /**
   * Callback when error is handled
   */
  onError?: (error: unknown, config: ReturnType<typeof getErrorMessageConfig>) => void
  /**
   * Callback for retry action
   */
  onRetry?: () => void | Promise<void>
  /**
   * Preserve error context for retry
   */
  preserveContext?: boolean
}

/**
 * Error context for retry
 */
export interface ErrorContext {
  /**
   * Original error
   */
  error: unknown
  /**
   * Error timestamp
   */
  timestamp: number
  /**
   * Retry attempt count
   */
  retryCount: number
  /**
   * Additional context data
   */
  context?: Record<string, unknown>
}

/**
 * useApiErrorHandler Hook
 *
 * Comprehensive API error handling with retry logic and recovery patterns.
 */
export function useApiErrorHandler() {
  const toastManager = useToastManager()
  const errorContextRef = useRef<ErrorContext | null>(null)
  const [retryAttempts, setRetryAttempts] = useState<Map<string, number>>(new Map())

  /**
   * Map error to ErrorCode
   */
  const mapErrorToCode = useCallback((error: unknown): ErrorCode => {
    if (isNetworkError(error)) {
      return ErrorCode.NETWORK_ERROR
    }

    if (isApiException(error)) {
      if (error.isAuthenticationError()) {
        return ErrorCode.UNAUTHORIZED
      }
      if (error.isAuthorizationError()) {
        return ErrorCode.FORBIDDEN
      }
      if (error.isNotFoundError()) {
        return ErrorCode.NOT_FOUND
      }
      if (error.isValidationError()) {
        return ErrorCode.VALIDATION_ERROR
      }
      if (error.isRateLimitError()) {
        return ErrorCode.RATE_LIMIT_EXCEEDED
      }
      if (error.isServerError()) {
        return ErrorCode.SERVER_ERROR
      }
    }

    return ErrorCode.UNKNOWN_ERROR
  }, [])

  /**
   * Calculate retry delay with exponential backoff
   */
  const calculateRetryDelay = useCallback((attempt: number, config: RetryConfig): number => {
    const delay = config.initialDelay * Math.pow(config.backoffMultiplier, attempt)
    return Math.min(delay, config.maxDelay)
  }, [])

  /**
   * Sleep utility for retry delays
   */
  const sleep = useCallback((ms: number): Promise<void> => {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }, [])

  /**
   * Automatic retry with exponential backoff
   */
  const retryWithBackoff = useCallback(
    async <T>(
      fn: () => Promise<T>,
      config: RetryConfig,
      errorId: string
    ): Promise<T> => {
      let lastError: unknown
      let attempt = 0

      while (attempt < config.maxRetries) {
        try {
          return await fn()
        } catch (error) {
          lastError = error
          attempt++

          // Check if we should retry
          if (!config.shouldRetry(error, attempt)) {
            throw error
          }

          // Calculate delay
          const delay = calculateRetryDelay(attempt - 1, config)

          // Update retry attempts
          setRetryAttempts((prev) => {
            const updated = new Map(prev)
            updated.set(errorId, attempt)
            return updated
          })

          // Wait before retrying
          await sleep(delay)
        }
      }

      throw lastError
    },
    [calculateRetryDelay, sleep]
  )

  /**
   * Handle API error
   */
  const handleError = useCallback(
    async (error: unknown, options: ApiErrorHandlerOptions = {}) => {
      const {
        showToast = true,
        logError = true,
        trackError = true,
        customMessage,
        customTitle,
        context,
        retryConfig: partialRetryConfig,
        autoRetry = false,
        onError,
        onRetry,
        preserveContext = false,
      } = options

      // Parse error if it's an AxiosError
      let parsedError: ApiException | NetworkError | unknown = error
      if (error instanceof FetchError) {
        parsedError = parseApiException(error)
      }

      // Get error configuration
      const errorConfig = getErrorMessageConfig(parsedError)
      const errorCode = mapErrorToCode(parsedError)
      const message = customMessage || getUserFriendlyErrorMessage(parsedError)
      const title = customTitle || getErrorTitle(parsedError)

      // Generate error ID
      const errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

      // Preserve error context if requested
      if (preserveContext) {
        errorContextRef.current = {
          error: parsedError,
          timestamp: Date.now(),
          retryCount: 0,
          context,
        }
      }

      // Log error
      if (logError) {
        console.error('[API Error Handler]', {
          error: parsedError,
          errorCode,
          category: errorConfig.category,
          severity: errorConfig.severity,
          message,
          title,
          context,
          errorId,
          ...(isApiException(parsedError) && {
            status: parsedError.status,
            code: parsedError.code,
            requestId: parsedError.requestId,
          }),
          ...(isNetworkError(parsedError) && {
            networkError: true,
          }),
        })
      }

      // Track error (e.g., Sentry)
      if (trackError && typeof window !== 'undefined') {
        if (window.Sentry) {
          window.Sentry.captureException(parsedError, {
            tags: {
              errorCode,
              category: errorConfig.category,
              severity: errorConfig.severity,
              errorId,
            },
            extra: {
              message,
              title,
              context,
              ...(isApiException(parsedError) && {
                status: parsedError.status,
                code: parsedError.code,
                requestId: parsedError.requestId,
              }),
            },
          })
        }
      }

      // Show toast notification
      if (showToast) {
        toastManager.addToast({
          message,
          severity: errorConfig.severity,
        })
      }

      // Call custom error handler
      if (onError) {
        onError(parsedError, errorConfig)
      }

      // Automatic retry for transient errors
      if (autoRetry && isRecoverableError(parsedError) && onRetry) {
        const config: RetryConfig = {
          ...DEFAULT_RETRY_CONFIG,
          ...partialRetryConfig,
        }

        try {
          await retryWithBackoff(
            async () => {
              await onRetry()
            },
            config,
            errorId
          )
        } catch (retryError) {
          // Retry failed, error already logged
          console.error('[API Error Handler] Retry failed:', retryError)
        }
      }

      return {
        error: parsedError,
        errorCode,
        config: errorConfig,
        message,
        title,
        errorId,
        isRecoverable: isRecoverableError(parsedError),
        retry: onRetry,
        retryCount: retryAttempts.get(errorId) || 0,
        context: errorContextRef.current,
      }
    },
    [toastManager, mapErrorToCode, retryWithBackoff, retryAttempts]
  )

  /**
   * Handle specific error types
   */
  const handleValidationError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Validation Error',
      })
    },
    [handleError]
  )

  const handleAuthenticationError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Authentication Required',
        showToast: true,
      })
    },
    [handleError]
  )

  const handleAuthorizationError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Access Denied',
        showToast: true,
      })
    },
    [handleError]
  )

  const handleNotFoundError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Not Found',
        showToast: false, // Usually don't show toast for 404s
      })
    },
    [handleError]
  )

  const handleRateLimitError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Rate Limit Exceeded',
        showToast: true,
      })
    },
    [handleError]
  )

  const handleServerError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Server Error',
        autoRetry: true, // Auto-retry server errors
        showToast: true,
      })
    },
    [handleError]
  )

  const handleNetworkError = useCallback(
    (error: unknown, options?: ApiErrorHandlerOptions) => {
      return handleError(error, {
        ...options,
        customTitle: 'Network Error',
        autoRetry: true, // Auto-retry network errors
        showToast: true,
      })
    },
    [handleError]
  )

  /**
   * Manual retry with context preservation
   */
  const retryWithContext = useCallback(
    async (retryFn: () => Promise<void> | void) => {
      if (!errorContextRef.current) {
        throw new Error('No error context available for retry')
      }

      const context = errorContextRef.current
      context.retryCount++

      try {
        await retryFn()
        // Clear context on success
        errorContextRef.current = null
      } catch (error) {
        // Update context with new error
        context.error = error
        context.timestamp = Date.now()
        throw error
      }
    },
    []
  )

  /**
   * Clear error context
   */
  const clearErrorContext = useCallback(() => {
    errorContextRef.current = null
  }, [])

  /**
   * Get current error context
   */
  const getErrorContext = useCallback((): ErrorContext | null => {
    return errorContextRef.current
  }, [])

  return {
    handleError,
    handleValidationError,
    handleAuthenticationError,
    handleAuthorizationError,
    handleNotFoundError,
    handleRateLimitError,
    handleServerError,
    handleNetworkError,
    mapErrorToCode,
    retryWithContext,
    clearErrorContext,
    getErrorContext,
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

