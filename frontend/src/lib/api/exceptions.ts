/**
 * API Exception Classes
 *
 * Exception classes for API error handling.
 */

import { FetchError } from './fetch'
import type { ApiErrorResponse } from './types'

/**
 * Field validation error
 */
export interface FieldError {
  /**
   * Field name
   */
  field: string
  /**
   * Error message
   */
  message: string
  /**
   * Error code
   */
  code: string
}

/**
 * API Exception class
 * Base exception class for API errors
 */
export class ApiException extends Error {
  /**
   * Error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
   */
  public readonly code: string
  /**
   * HTTP status code
   */
  public readonly status: number
  /**
   * Request ID for tracing
   */
  public readonly requestId?: string
  /**
   * Error timestamp
   */
  public readonly timestamp?: string
  /**
   * Additional error details
   */
  public readonly details?: Record<string, any>
  /**
   * Field-specific validation errors
   */
  public readonly fieldErrors?: FieldError[]
  /**
   * Original Fetch error
   */
  public readonly originalError?: FetchError | Error

  constructor(
    message: string,
    code: string,
    status: number,
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      fieldErrors?: FieldError[]
      originalError?: FetchError | Error
    }
  ) {
    super(message)
    this.name = 'ApiException'
    this.code = code
    this.status = status
    this.requestId = options?.requestId
    this.timestamp = options?.timestamp
    this.details = options?.details
    this.fieldErrors = options?.fieldErrors
    this.originalError = options?.originalError

    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiException)
    }
  }

  /**
   * Check if this is a validation error
   */
  public isValidationError(): boolean {
    return this.code === 'VALIDATION_ERROR' || this.status === 400
  }

  /**
   * Check if this is an authentication error
   */
  public isAuthenticationError(): boolean {
    return this.code === 'UNAUTHORIZED' || this.status === 401
  }

  /**
   * Check if this is an authorization error
   */
  public isAuthorizationError(): boolean {
    return this.code === 'FORBIDDEN' || this.status === 403
  }

  /**
   * Check if this is a not found error
   */
  public isNotFoundError(): boolean {
    return this.code === 'NOT_FOUND' || this.status === 404
  }

  /**
   * Check if this is a rate limit error
   */
  public isRateLimitError(): boolean {
    return this.code === 'RATE_LIMIT_EXCEEDED' || this.status === 429
  }

  /**
   * Check if this is a server error
   */
  public isServerError(): boolean {
    return this.status >= 500 && this.status < 600
  }

  /**
   * Get field error for a specific field
   */
  public getFieldError(fieldName: string): FieldError | undefined {
    return this.fieldErrors?.find((error) => error.field === fieldName)
  }

  /**
   * Get all field error messages as a map
   */
  public getFieldErrorsMap(): Record<string, string> {
    if (!this.fieldErrors) return {}
    return this.fieldErrors.reduce(
      (acc, error) => {
        acc[error.field] = error.message
        return acc
      },
      {} as Record<string, string>
    )
  }

  /**
   * Convert to JSON for logging
   */
  public toJSON(): Record<string, any> {
    return {
      name: this.name,
      message: this.message,
      code: this.code,
      status: this.status,
      requestId: this.requestId,
      timestamp: this.timestamp,
      details: this.details,
      fieldErrors: this.fieldErrors,
    }
  }
}

/**
 * Validation Exception
 * Thrown when request validation fails
 */
export class ValidationException extends ApiException {
  constructor(
    message: string,
    fieldErrors?: FieldError[],
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      originalError?: FetchError | Error
    }
  ) {
    super(message, 'VALIDATION_ERROR', 400, {
      ...options,
      fieldErrors,
    })
    this.name = 'ValidationException'
  }
}

/**
 * Authentication Exception
 * Thrown when authentication fails
 */
export class AuthenticationException extends ApiException {
  constructor(
    message: string = 'Authentication required',
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      originalError?: FetchError | Error
    }
  ) {
    super(message, 'UNAUTHORIZED', 401, options)
    this.name = 'AuthenticationException'
  }
}

/**
 * Authorization Exception
 * Thrown when user lacks required permissions
 */
export class AuthorizationException extends ApiException {
  constructor(
    message: string = 'Insufficient permissions',
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      originalError?: FetchError | Error
    }
  ) {
    super(message, 'FORBIDDEN', 403, options)
    this.name = 'AuthorizationException'
  }
}

/**
 * Not Found Exception
 * Thrown when resource is not found
 */
export class NotFoundException extends ApiException {
  constructor(
    message: string = 'Resource not found',
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      originalError?: FetchError | Error
    }
  ) {
    super(message, 'NOT_FOUND', 404, options)
    this.name = 'NotFoundException'
  }
}

/**
 * Rate Limit Exception
 * Thrown when rate limit is exceeded
 */
export class RateLimitException extends ApiException {
  public readonly retryAfter?: number

  constructor(
    message: string = 'Rate limit exceeded',
    retryAfter?: number,
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      originalError?: FetchError | Error
    }
  ) {
    super(message, 'RATE_LIMIT_EXCEEDED', 429, options)
    this.name = 'RateLimitException'
    this.retryAfter = retryAfter
  }
}

/**
 * Server Exception
 * Thrown when server error occurs
 */
export class ServerException extends ApiException {
  constructor(
    message: string = 'Internal server error',
    status: number = 500,
    options?: {
      requestId?: string
      timestamp?: string
      details?: Record<string, any>
      originalError?: FetchError | Error
    }
  ) {
    super(message, 'INTERNAL_SERVER_ERROR', status, options)
    this.name = 'ServerException'
  }
}

/**
 * Parse API error response to ApiException
 */
export function parseApiException(error: FetchError | Error): ApiException {
  const fetchError = error instanceof FetchError ? error : null

  if (!fetchError?.response) {
    return new ServerException(
      error.message || 'Network error occurred',
      0,
      { originalError: error }
    )
  }

  const response = fetchError.response
  const status = response.status
  const data = response.data as ApiErrorResponse | string

  // Try to parse error response
  if (typeof data === 'object' && data !== null && 'error' in data) {
    const errorData = data.error
    const fieldErrors = errorData.details?.field_errors

    // Create appropriate exception based on status code
    switch (status) {
      case 400:
        return new ValidationException(
          errorData.message || 'Validation failed',
          fieldErrors,
          {
            requestId: errorData.request_id || response.headers.get('x-request-id') || undefined,
            timestamp: errorData.timestamp,
            details: errorData.details,
            originalError: error,
          }
        )

      case 401:
        return new AuthenticationException(errorData.message, {
          requestId: errorData.request_id || response.headers['x-request-id'],
          timestamp: errorData.timestamp,
          details: errorData.details,
          originalError: error,
        })

      case 403:
        return new AuthorizationException(errorData.message, {
          requestId: errorData.request_id || response.headers['x-request-id'],
          timestamp: errorData.timestamp,
          details: errorData.details,
          originalError: error,
        })

      case 404:
        return new NotFoundException(errorData.message, {
          requestId: errorData.request_id || response.headers['x-request-id'],
          timestamp: errorData.timestamp,
          details: errorData.details,
          originalError: error,
        })

      case 429: {
        const retryAfter = response.headers.get('retry-after')
        const retryAfterSeconds = retryAfter
          ? parseInt(retryAfter, 10)
          : undefined
        return new RateLimitException(
          errorData.message || 'Rate limit exceeded',
          retryAfterSeconds,
          {
            requestId: errorData.request_id || response.headers.get('x-request-id') || undefined,
            timestamp: errorData.timestamp,
            details: errorData.details,
            originalError: error,
          }
        )
      }

      case 500:
      case 502:
      case 503:
      case 504:
        return new ServerException(errorData.message || 'Server error', status, {
          requestId: errorData.request_id || response.headers['x-request-id'],
          timestamp: errorData.timestamp,
          details: errorData.details,
          originalError: error,
        })

      default:
        return new ApiException(
          errorData.message || `API error: ${status}`,
          errorData.code || `HTTP_${status}`,
          status,
          {
            requestId: errorData.request_id || response.headers.get('x-request-id') || undefined,
            timestamp: errorData.timestamp,
            details: errorData.details,
            fieldErrors,
            originalError: error,
          }
        )
    }
  }

  // Fallback for non-standard error responses
  const message =
    typeof data === 'string' ? data : `API error: ${status} ${response.statusText}`
  return new ApiException(
    message,
    `HTTP_${status}`,
    status,
    {
      requestId: response.headers.get('x-request-id') || undefined,
      originalError: error,
    }
  )
}

/**
 * Check if error is an ApiException
 */
export function isApiException(error: unknown): error is ApiException {
  return error instanceof ApiException
}

/**
 * Check if error is a specific exception type
 */
export function isExceptionType<T extends ApiException>(
  error: unknown,
  exceptionClass: new (...args: any[]) => T
): error is T {
  return error instanceof exceptionClass
}

