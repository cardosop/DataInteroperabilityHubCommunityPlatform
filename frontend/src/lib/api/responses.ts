/**
 * API Response Types
 *
 * Type definitions for standardized API response formats.
 */

/**
 * Standard API response wrapper
 * Used for single resource responses and simple data responses
 */
export interface ApiResponse<T = any> {
  /**
   * Response data
   */
  data?: T
  /**
   * Optional success message
   */
  message?: string
  /**
   * Optional metadata
   */
  metadata?: Record<string, any>
  /**
   * Request ID for tracing
   */
  requestId?: string
  /**
   * Response timestamp
   */
  timestamp?: string
}

/**
 * Pagination metadata for page-based pagination
 */
export interface PaginationMetadata {
  /**
   * Total number of items
   */
  count: number
  /**
   * Current page number (1-indexed)
   */
  page: number
  /**
   * Number of items per page
   */
  page_size: number
  /**
   * Total number of pages
   */
  total_pages: number
  /**
   * URL for next page (null if no next page)
   */
  next: string | null
  /**
   * URL for previous page (null if no previous page)
   */
  previous: string | null
}

/**
 * Paginated response for page-based pagination
 * Used for list endpoints with offset-based pagination
 */
export interface PaginatedResponse<T = any> extends PaginationMetadata {
  /**
   * Array of items in the current page
   */
  results: T[]
  /**
   * Optional metadata
   */
  metadata?: Record<string, any>
  /**
   * Request ID for tracing
   */
  requestId?: string
  /**
   * Response timestamp
   */
  timestamp?: string
}

/**
 * Cursor pagination metadata
 */
export interface CursorPaginationMetadata {
  /**
   * Total number of items (may be null for cursor-based pagination)
   */
  count: number | null
  /**
   * Number of items per page
   */
  page_size: number
  /**
   * Cursor for next page (null if no next page)
   */
  next_cursor: string | null
  /**
   * Cursor for previous page (null if no previous page)
   */
  previous_cursor: string | null
}

/**
 * Cursor-paginated response for cursor-based pagination
 * Used for list endpoints with cursor-based pagination
 */
export interface CursorPaginatedResponse<T = any> extends CursorPaginationMetadata {
  /**
   * Array of items in the current page
   */
  results: T[]
  /**
   * Optional metadata
   */
  metadata?: Record<string, any>
  /**
   * Request ID for tracing
   */
  requestId?: string
  /**
   * Response timestamp
   */
  timestamp?: string
}

/**
 * Type guard to check if response is paginated
 */
export function isPaginatedResponse<T>(
  response: ApiResponse<T> | PaginatedResponse<T> | CursorPaginatedResponse<T>
): response is PaginatedResponse<T> {
  return (
    'results' in response &&
    'page' in response &&
    'total_pages' in response &&
    'next' in response &&
    'previous' in response
  )
}

/**
 * Type guard to check if response is cursor-paginated
 */
export function isCursorPaginatedResponse<T>(
  response: ApiResponse<T> | PaginatedResponse<T> | CursorPaginatedResponse<T>
): response is CursorPaginatedResponse<T> {
  return (
    'results' in response &&
    'next_cursor' in response &&
    'previous_cursor' in response &&
    !('page' in response)
  )
}

/**
 * Type guard to check if response is a simple API response
 */
export function isApiResponse<T>(
  response: ApiResponse<T> | PaginatedResponse<T> | CursorPaginatedResponse<T>
): response is ApiResponse<T> {
  return !isPaginatedResponse(response) && !isCursorPaginatedResponse(response)
}

/**
 * Extract data from any response type
 */
export function extractResponseData<T>(
  response: ApiResponse<T> | PaginatedResponse<T> | CursorPaginatedResponse<T>
): T | T[] {
  if (isPaginatedResponse(response) || isCursorPaginatedResponse(response)) {
    return response.results
  }
  return response.data as T
}

