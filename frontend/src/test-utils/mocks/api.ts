/**
 * Mock API Utilities
 *
 * Utilities for mocking API calls in tests.
 * Provides helpers for creating mock API responses, errors, and handlers.
 */

import { FetchError, FetchResponse } from '@/lib/api/fetch'
import type { ExtendedFetchRequestInit } from '@/lib/api/types'
import { PaginatedResponse } from '@/lib/api/responses'

/**
 * Create a mock Fetch response
 *
 * @param data - Response data
 * @param status - HTTP status code
 * @param headers - Response headers
 * @returns Mock Fetch response
 *
 * @example
 * ```tsx
 * const mockResponse = createMockResponse({ id: '1', name: 'Test' }, 200)
 * ```
 */
export function createMockResponse<T>(
  data: T,
  status: number = 200,
  headers: Record<string, string> = {}
): FetchResponse<T> {
  const headerMap = new Headers()
  headerMap.set('content-type', 'application/json')
  Object.entries(headers).forEach(([key, value]) => {
    headerMap.set(key, value)
  })

  return {
    data,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: headerMap,
    config: {} as ExtendedFetchRequestInit,
  }
}

/**
 * Create a mock paginated response
 *
 * @param items - Array of items
 * @param page - Current page number
 * @param pageSize - Page size
 * @param total - Total number of items
 * @returns Mock paginated response
 *
 * @example
 * ```tsx
 * const mockPaginatedResponse = createMockPaginatedResponse(
 *   [{ id: '1' }, { id: '2' }],
 *   1,
 *   10,
 *   2
 * )
 * ```
 */
export function createMockPaginatedResponse<T>(
  items: T[],
  page: number = 1,
  pageSize: number = items.length,
  total: number = items.length
): PaginatedResponse<T> {
  return {
    count: total,
    next: page * pageSize < total ? `?page=${page + 1}` : null,
    previous: page > 1 ? `?page=${page - 1}` : null,
    results: items,
  }
}

/**
 * Create a mock Fetch error
 *
 * @param message - Error message
 * @param status - HTTP status code
 * @param data - Error response data
 * @param config - Request config
 * @returns Mock Fetch error
 *
 * @example
 * ```tsx
 * const mockError = createMockError('Not found', 404, {
 *   error: { message: 'Resource not found', code: 'NOT_FOUND' }
 * })
 * ```
 */
export function createMockError(
  message: string = 'Request failed',
  status: number = 500,
  data?: any,
  config?: ExtendedFetchRequestInit
): FetchError {
  const response = data
    ? createMockResponse(data, status)
    : createMockResponse({ error: { message, code: `HTTP_${status}` } }, status)

  return new FetchError(message, config, undefined, response)
}

/**
 * Create a mock network error (no response)
 *
 * @param message - Error message
 * @param config - Request config
 * @returns Mock Fetch network error
 *
 * @example
 * ```tsx
 * const mockNetworkError = createMockNetworkError('Network error')
 * ```
 */
export function createMockNetworkError(
  message: string = 'Network Error',
  config?: ExtendedFetchRequestInit
): FetchError {
  // No response property for network errors
  return new FetchError(message, config)
}

/**
 * Create a mock API error response
 *
 * @param message - Error message
 * @param code - Error code
 * @param status - HTTP status code
 * @param details - Additional error details
 * @returns Mock API error response
 *
 * @example
 * ```tsx
 * const mockApiError = createMockApiErrorResponse(
 *   'Validation failed',
 *   'VALIDATION_ERROR',
 *   400,
 *   { field_errors: [{ field: 'name', message: 'Required' }] }
 * )
 * ```
 */
export function createMockApiErrorResponse(
  message: string,
  code: string,
  status: number,
  details?: Record<string, any>
) {
  return {
    error: {
      message,
      code,
      request_id: `test-request-${Date.now()}`,
      timestamp: new Date().toISOString(),
      details,
    },
  }
}

/**
 * Mock API client type
 * Use this type when creating mock API clients in tests
 *
 * @example
 * ```tsx
 * import { vi } from 'vitest'
 * import type { MockApiClient } from '@/test-utils'
 *
 * const mockApiClient: MockApiClient = {
 *   get: vi.fn(),
 *   post: vi.fn(),
 *   put: vi.fn(),
 *   patch: vi.fn(),
 *   delete: vi.fn(),
 *   request: vi.fn(),
 * }
 * ```
 */
export interface MockApiClient {
  get: any // Mock function from vi.fn() - import vi from 'vitest' in test files
  post: any
  put: any
  patch: any
  delete: any
  request: any
}

// Note: vi must be imported from 'vitest' in the test file where this type is used

