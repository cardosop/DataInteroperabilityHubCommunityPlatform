/**
 * API Error Handling
 *
 * Utilities for handling and formatting API errors.
 */

import { FetchError } from './fetch'
import type { ApiErrorResponse } from './types'

/**
 * @deprecated Use ApiException from './exceptions' instead
 * This class is kept for backward compatibility
 */

/**
 * API Error class
 */
export class ApiError extends Error {
  public readonly code: string
  public readonly status: number
  public readonly details?: Record<string, any>
  public readonly requestId?: string
  public readonly originalError: FetchError | Error

  constructor(
    message: string,
    code: string,
    status: number,
    originalError: FetchError | Error,
    details?: Record<string, any>,
    requestId?: string
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
    this.requestId = requestId
    this.originalError = originalError

    // Maintain proper stack trace
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ApiError)
    }
  }
}

/**
 * Network Error class
 */
export class NetworkError extends Error {
  public readonly originalError: FetchError | Error

  constructor(message: string, originalError: FetchError | Error) {
    super(message)
    this.name = 'NetworkError'
    this.originalError = originalError

    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, NetworkError)
    }
  }
}

/**
 * Parse API error from Fetch error
 */
export function parseApiError(error: FetchError | Error): ApiError | NetworkError {
  // Check if it's a FetchError
  const fetchError = error instanceof FetchError ? error : null

  // Network error (no response)
  if (!fetchError?.response) {
    return new NetworkError(
      error.message || 'Network error occurred',
      error
    )
  }

  // API error (has response)
  const response = fetchError.response
  const status = response.status
  const data = response.data as ApiErrorResponse | string

  // Try to parse error response
  if (typeof data === 'object' && data !== null && 'error' in data) {
    const errorData = data.error
    const requestId = response.headers.get('x-request-id')
    return new ApiError(
      errorData.message || `API error: ${status}`,
      errorData.code || `HTTP_${status}`,
      status,
      error,
      errorData.details,
      errorData.requestId || requestId || undefined
    )
  }

  // Fallback for non-standard error responses
  const message =
    typeof data === 'string' ? data : `API error: ${status} ${response.statusText}`
  const requestId = response.headers.get('x-request-id')
  return new ApiError(
    message,
    `HTTP_${status}`,
    status,
    error,
    undefined,
    requestId || undefined
  )
}

/**
 * Check if error is an API error
 */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

/**
 * Check if error is a network error
 */
export function isNetworkError(error: unknown): error is NetworkError {
  return error instanceof NetworkError
}

/**
 * Get user-friendly error message
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.message
  }
  if (isNetworkError(error)) {
    return 'Network error. Please check your connection and try again.'
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred'
}

