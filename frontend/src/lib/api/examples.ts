/**
 * API Types Usage Examples
 *
 * Examples demonstrating how to use API response types and exceptions.
 */

import { apiClient } from './client'
import {
  ApiResponse,
  PaginatedResponse,
  CursorPaginatedResponse,
  isPaginatedResponse,
  isCursorPaginatedResponse,
  extractResponseData,
} from './responses'
import {
  ApiException,
  ValidationException,
  AuthenticationException,
  parseApiException,
  isApiException,
} from './exceptions'

/**
 * Example: Fetching a single resource
 */
export async function fetchUser(userId: string): Promise<ApiResponse<{ id: string; name: string }>> {
  const response = await apiClient.get(`/users/${userId}`)
  return response.data as ApiResponse<{ id: string; name: string }>
}

/**
 * Example: Fetching paginated resources (page-based)
 */
export async function fetchUsers(
  page: number = 1,
  pageSize: number = 50
): Promise<PaginatedResponse<{ id: string; name: string }>> {
  const response = await apiClient.get('/users', {
    params: { page, page_size: pageSize },
  })
  return response.data as PaginatedResponse<{ id: string; name: string }>
}

/**
 * Example: Fetching cursor-paginated resources
 */
export async function fetchAssets(
  cursor?: string,
  pageSize: number = 50
): Promise<CursorPaginatedResponse<{ id: string; name: string }>> {
  const response = await apiClient.get('/assets', {
    params: { cursor, page_size: pageSize },
  })
  return response.data as CursorPaginatedResponse<{ id: string; name: string }>
}

/**
 * Example: Handling different response types
 */
export async function handleResponse() {
  try {
    const response = await apiClient.get('/data')

    // Check response type
    if (isPaginatedResponse(response.data)) {
      // Handle paginated response
      const { results, page, total_pages, next, previous } = response.data
      console.log(`Page ${page} of ${total_pages}`)
      console.log(`Items: ${results.length}`)
      if (next) {
        console.log('Has next page')
      }
    } else if (isCursorPaginatedResponse(response.data)) {
      // Handle cursor-paginated response
      const { results, next_cursor, previous_cursor } = response.data
      console.log(`Items: ${results.length}`)
      if (next_cursor) {
        console.log('Has next page')
      }
    } else {
      // Handle simple API response
      const data = extractResponseData(response.data)
      console.log('Data:', data)
    }
  } catch (error) {
    const exception = parseApiException(error as any)
    handleException(exception)
  }
}

/**
 * Example: Error handling with exceptions
 */
export function handleException(exception: ApiException) {
  if (exception.isValidationError()) {
    // Handle validation errors
    const fieldErrors = exception.getFieldErrorsMap()
    console.error('Validation errors:', fieldErrors)

    // Show field-specific errors
    exception.fieldErrors?.forEach((error) => {
      console.error(`${error.field}: ${error.message}`)
    })
  } else if (exception.isAuthenticationError()) {
    // Handle authentication errors
    console.error('Authentication required')
    // Redirect to login
  } else if (exception.isAuthorizationError()) {
    // Handle authorization errors
    console.error('Insufficient permissions')
  } else if (exception.isNotFoundError()) {
    // Handle not found errors
    console.error('Resource not found')
  } else if (exception.isRateLimitError()) {
    // Handle rate limit errors
    console.error(`Rate limited. Retry after ${exception.retryAfter} seconds`)
  } else if (exception.isServerError()) {
    // Handle server errors
    console.error('Server error occurred')
  }
}

/**
 * Example: Creating a resource with validation error handling
 */
export async function createUser(userData: { name: string; email: string }) {
  try {
    const response = await apiClient.post('/users', userData)
    return response.data as ApiResponse<{ id: string; name: string; email: string }>
  } catch (error) {
    const exception = parseApiException(error as any)

    if (exception instanceof ValidationException) {
      // Handle validation errors
      const fieldErrors = exception.getFieldErrorsMap()
      throw new Error(`Validation failed: ${JSON.stringify(fieldErrors)}`)
    }

    throw exception
  }
}

/**
 * Example: Type-safe API call helper
 */
export async function apiCall<T>(
  endpoint: string,
  options?: { method?: 'GET' | 'POST' | 'PUT' | 'DELETE'; data?: any }
): Promise<ApiResponse<T>> {
  try {
    const response = await apiClient({
      url: endpoint,
      method: options?.method || 'GET',
      data: options?.data,
    })
    return response.data as ApiResponse<T>
  } catch (error) {
    const exception = parseApiException(error as any)
    throw exception
  }
}

/**
 * Example: Paginated API call helper
 */
export async function paginatedApiCall<T>(
  endpoint: string,
  page: number = 1,
  pageSize: number = 50
): Promise<PaginatedResponse<T>> {
  try {
    const response = await apiClient.get(endpoint, {
      params: { page, page_size: pageSize },
    })
    return response.data as PaginatedResponse<T>
  } catch (error) {
    const exception = parseApiException(error as any)
    throw exception
  }
}

/**
 * Example: Cursor-paginated API call helper
 */
export async function cursorPaginatedApiCall<T>(
  endpoint: string,
  cursor?: string,
  pageSize: number = 50
): Promise<CursorPaginatedResponse<T>> {
  try {
    const response = await apiClient.get(endpoint, {
      params: { cursor, page_size: pageSize },
    })
    return response.data as CursorPaginatedResponse<T>
  } catch (error) {
    const exception = parseApiException(error as any)
    throw exception
  }
}

