/**
 * Error Message Mapping
 *
 * Maps error codes and types to user-friendly error messages.
 */

import { ApiError, NetworkError, isApiError, isNetworkError } from '@/lib/api/errors'
import { ApiException, isApiException } from '@/lib/api/exceptions'

export type ErrorCategory =
  | 'network'
  | 'authentication'
  | 'authorization'
  | 'validation'
  | 'notFound'
  | 'server'
  | 'timeout'
  | 'rateLimit'
  | 'unknown'

export interface ErrorMessageConfig {
  title: string
  message: string
  action?: string
  severity: 'error' | 'warning' | 'info'
  category: ErrorCategory
}

/**
 * Error message mapping configuration
 */
const ERROR_MESSAGE_MAP: Record<string, ErrorMessageConfig> = {
  // Network Errors
  NETWORK_ERROR: {
    title: 'Connection Problem',
    message: "We're having trouble connecting. Please check your internet connection and try again.",
    action: 'Retry',
    severity: 'error',
    category: 'network',
  },
  TIMEOUT: {
    title: 'Request Timeout',
    message: 'The request took too long to complete. Please try again.',
    action: 'Retry',
    severity: 'error',
    category: 'timeout',
  },
  OFFLINE: {
    title: 'You\'re Offline',
    message: 'It looks like you\'re not connected to the internet. Please check your connection and try again.',
    action: 'Retry',
    severity: 'warning',
    category: 'network',
  },

  // Authentication Errors
  UNAUTHORIZED: {
    title: 'Session Expired',
    message: 'Your session has expired. Please sign in again to continue.',
    action: 'Sign In',
    severity: 'warning',
    category: 'authentication',
  },
  AUTHENTICATION_FAILED: {
    title: 'Authentication Failed',
    message: 'We couldn\'t verify your identity. Please check your credentials and try again.',
    action: 'Retry',
    severity: 'error',
    category: 'authentication',
  },
  TOKEN_EXPIRED: {
    title: 'Session Expired',
    message: 'Your session has expired. Please sign in again.',
    action: 'Sign In',
    severity: 'warning',
    category: 'authentication',
  },

  // Authorization Errors
  FORBIDDEN: {
    title: 'Access Denied',
    message: 'You don\'t have permission to perform this action. Contact your administrator if you need access.',
    action: 'Contact Support',
    severity: 'error',
    category: 'authorization',
  },
  PERMISSION_DENIED: {
    title: 'Permission Denied',
    message: 'You don\'t have the required permissions for this operation.',
    action: 'Contact Support',
    severity: 'error',
    category: 'authorization',
  },

  // Validation Errors
  VALIDATION_ERROR: {
    title: 'Validation Error',
    message: 'Please check your input. Some fields need to be corrected.',
    action: 'Review',
    severity: 'warning',
    category: 'validation',
  },
  INVALID_INPUT: {
    title: 'Invalid Input',
    message: 'The information you provided is not valid. Please check and try again.',
    action: 'Review',
    severity: 'warning',
    category: 'validation',
  },
  REQUIRED_FIELD: {
    title: 'Missing Information',
    message: 'Some required fields are missing. Please fill them in and try again.',
    action: 'Review',
    severity: 'warning',
    category: 'validation',
  },

  // Not Found Errors
  NOT_FOUND: {
    title: 'Not Found',
    message: 'We couldn\'t find what you\'re looking for. It may have been moved or deleted.',
    action: 'Go Back',
    severity: 'info',
    category: 'notFound',
  },
  RESOURCE_NOT_FOUND: {
    title: 'Resource Not Found',
    message: 'The requested resource could not be found.',
    action: 'Go Back',
    severity: 'info',
    category: 'notFound',
  },

  // Server Errors
  INTERNAL_SERVER_ERROR: {
    title: 'Server Error',
    message: 'Something went wrong on our end. We\'ve been notified and are working on it. Please try again in a few moments.',
    action: 'Retry',
    severity: 'error',
    category: 'server',
  },
  SERVICE_UNAVAILABLE: {
    title: 'Service Unavailable',
    message: 'The service is temporarily unavailable. Please try again later.',
    action: 'Retry',
    severity: 'error',
    category: 'server',
  },
  BAD_GATEWAY: {
    title: 'Service Error',
    message: 'We\'re experiencing technical difficulties. Please try again in a moment.',
    action: 'Retry',
    severity: 'error',
    category: 'server',
  },

  // Rate Limiting
  RATE_LIMIT_EXCEEDED: {
    title: 'Too Many Requests',
    message: 'You\'ve made too many requests. Please wait a moment and try again.',
    action: 'Wait',
    severity: 'warning',
    category: 'rateLimit',
  },
  TOO_MANY_REQUESTS: {
    title: 'Rate Limit Exceeded',
    message: 'Please slow down. You\'re making requests too quickly.',
    action: 'Wait',
    severity: 'warning',
    category: 'rateLimit',
  },

  // Unknown Errors
  UNKNOWN_ERROR: {
    title: 'Something Went Wrong',
    message: 'An unexpected error occurred. Please try again, or contact support if the problem persists.',
    action: 'Contact Support',
    severity: 'error',
    category: 'unknown',
  },
}

/**
 * HTTP status code to error code mapping
 */
const HTTP_STATUS_MAP: Record<number, string> = {
  400: 'VALIDATION_ERROR',
  401: 'UNAUTHORIZED',
  403: 'FORBIDDEN',
  404: 'NOT_FOUND',
  408: 'TIMEOUT',
  429: 'RATE_LIMIT_EXCEEDED',
  500: 'INTERNAL_SERVER_ERROR',
  502: 'BAD_GATEWAY',
  503: 'SERVICE_UNAVAILABLE',
  504: 'TIMEOUT',
}

/**
 * Get error message configuration from error
 */
export function getErrorMessageConfig(error: unknown): ErrorMessageConfig {
  // Handle ApiException (preferred)
  if (isApiException(error)) {
    const errorCode = error.code.toUpperCase()

    // Check direct code match
    if (ERROR_MESSAGE_MAP[errorCode]) {
      return ERROR_MESSAGE_MAP[errorCode]
    }

    // Check HTTP status code mapping
    if (HTTP_STATUS_MAP[error.status]) {
      const mappedCode = HTTP_STATUS_MAP[error.status]
      if (ERROR_MESSAGE_MAP[mappedCode]) {
        return ERROR_MESSAGE_MAP[mappedCode]
      }
    }

    // Use server error for 5xx status codes
    if (error.status >= 500) {
      return ERROR_MESSAGE_MAP.INTERNAL_SERVER_ERROR
    }

    // Use validation error for 4xx status codes
    if (error.status >= 400 && error.status < 500) {
      return ERROR_MESSAGE_MAP.VALIDATION_ERROR
    }
  }

  // Handle API errors (legacy)
  if (isApiError(error)) {
    const errorCode = error.code.toUpperCase()

    // Check direct code match
    if (ERROR_MESSAGE_MAP[errorCode]) {
      return ERROR_MESSAGE_MAP[errorCode]
    }

    // Check HTTP status code mapping
    if (HTTP_STATUS_MAP[error.status]) {
      const mappedCode = HTTP_STATUS_MAP[error.status]
      if (ERROR_MESSAGE_MAP[mappedCode]) {
        return ERROR_MESSAGE_MAP[mappedCode]
      }
    }

    // Check for common error patterns in code
    if (errorCode.includes('NETWORK') || errorCode.includes('CONNECTION')) {
      return ERROR_MESSAGE_MAP.NETWORK_ERROR
    }
    if (errorCode.includes('TIMEOUT')) {
      return ERROR_MESSAGE_MAP.TIMEOUT
    }
    if (errorCode.includes('VALIDATION') || errorCode.includes('INVALID')) {
      return ERROR_MESSAGE_MAP.VALIDATION_ERROR
    }
    if (errorCode.includes('AUTH') || errorCode.includes('UNAUTHORIZED')) {
      return ERROR_MESSAGE_MAP.UNAUTHORIZED
    }
    if (errorCode.includes('FORBIDDEN') || errorCode.includes('PERMISSION')) {
      return ERROR_MESSAGE_MAP.FORBIDDEN
    }
    if (errorCode.includes('NOT_FOUND') || errorCode.includes('404')) {
      return ERROR_MESSAGE_MAP.NOT_FOUND
    }

    // Use server error for 5xx status codes
    if (error.status >= 500) {
      return ERROR_MESSAGE_MAP.INTERNAL_SERVER_ERROR
    }

    // Use validation error for 4xx status codes
    if (error.status >= 400 && error.status < 500) {
      return ERROR_MESSAGE_MAP.VALIDATION_ERROR
    }
  }

  // Handle network errors
  if (isNetworkError(error)) {
    // Check if offline
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      return ERROR_MESSAGE_MAP.OFFLINE
    }
    return ERROR_MESSAGE_MAP.NETWORK_ERROR
  }

  // Handle generic Error objects
  if (error instanceof Error) {
    const errorMessage = error.message.toUpperCase()

    if (errorMessage.includes('NETWORK') || errorMessage.includes('FETCH')) {
      return ERROR_MESSAGE_MAP.NETWORK_ERROR
    }
    if (errorMessage.includes('TIMEOUT')) {
      return ERROR_MESSAGE_MAP.TIMEOUT
    }
    if (errorMessage.includes('UNAUTHORIZED') || errorMessage.includes('AUTH')) {
      return ERROR_MESSAGE_MAP.UNAUTHORIZED
    }
    if (errorMessage.includes('FORBIDDEN') || errorMessage.includes('PERMISSION')) {
      return ERROR_MESSAGE_MAP.FORBIDDEN
    }
  }

  // Default to unknown error
  return ERROR_MESSAGE_MAP.UNKNOWN_ERROR
}

/**
 * Get user-friendly error message
 */
export function getUserFriendlyErrorMessage(error: unknown): string {
  const config = getErrorMessageConfig(error)
  return config.message
}

/**
 * Get error title
 */
export function getErrorTitle(error: unknown): string {
  const config = getErrorMessageConfig(error)
  return config.title
}

/**
 * Get error category
 */
export function getErrorCategory(error: unknown): ErrorCategory {
  const config = getErrorMessageConfig(error)
  return config.category
}

/**
 * Get error severity
 */
export function getErrorSeverity(error: unknown): 'error' | 'warning' | 'info' {
  const config = getErrorMessageConfig(error)
  return config.severity
}

/**
 * Check if error is recoverable
 */
export function isRecoverableError(error: unknown): boolean {
  const category = getErrorCategory(error)
  return ['network', 'timeout', 'server', 'rateLimit'].includes(category)
}

