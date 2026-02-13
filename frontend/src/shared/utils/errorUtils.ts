/**
 * Error Utilities
 * Functions for normalizing and handling errors consistently across the application
 */

import type { ApiError } from '../types/api';

/**
 * Normalizes various error inputs into a consistent ApiError shape
 *
 * @param err - Error input (Error instance, string, ApiError from client, or unknown)
 * @returns Normalized ApiError with all required fields
 */
export function normalizeError(err: unknown): ApiError {
  // Already an ApiError (from apiClient)
  if (err && typeof err === 'object' && 'error' in err) {
    const apiError = err as ApiError;
    // Ensure all required fields are present
    return {
      error: {
        code: apiError.error.code || 'UNKNOWN_ERROR',
        message: apiError.error.message || 'An error occurred',
        http_status: apiError.error.http_status || 500,
        request_id: apiError.error.request_id || 'unknown',
        timestamp: apiError.error.timestamp || new Date().toISOString(),
        details: apiError.error.details,
        field_errors: apiError.error.field_errors,
      },
    };
  }

  // JavaScript Error instance
  if (err instanceof Error) {
    return {
      error: {
        code: 'JAVASCRIPT_ERROR',
        message: err.message || 'An unexpected error occurred',
        http_status: 500,
        request_id: 'unknown',
        timestamp: new Date().toISOString(),
        details: {
          name: err.name,
          stack: err.stack,
        },
      },
    };
  }

  // String error
  if (typeof err === 'string') {
    return {
      error: {
        code: 'STRING_ERROR',
        message: err || 'An error occurred',
        http_status: 500,
        request_id: 'unknown',
        timestamp: new Date().toISOString(),
      },
    };
  }

  // Unknown error type
  return {
    error: {
      code: 'UNKNOWN_ERROR',
      message: 'An unexpected error occurred',
      http_status: 500,
      request_id: 'unknown',
      timestamp: new Date().toISOString(),
      details: {
        original: String(err),
      },
    },
  };
}
