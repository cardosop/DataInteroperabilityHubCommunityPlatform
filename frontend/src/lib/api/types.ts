/**
 * API Client Types
 *
 * Type definitions for API client configuration and interceptors.
 */

/**
 * Request ID generator function type
 */
export type RequestIdGenerator = () => string

/**
 * Tenant ID getter function type
 */
export type TenantIdGetter = () => string | null

/**
 * Token refresh function type
 */
export type TokenRefreshFunction = () => Promise<string | null>

/**
 * Rate limit handler function type
 */
export type RateLimitHandler = (retryAfter: number) => void

/**
 * Retry configuration
 */
export interface RetryConfig {
  /**
   * Maximum number of retry attempts
   * @default 3
   */
  maxRetries?: number
  /**
   * Initial delay in milliseconds
   * @default 1000
   */
  initialDelay?: number
  /**
   * Maximum delay in milliseconds
   * @default 10000
   */
  maxDelay?: number
  /**
   * Multiplier for exponential backoff
   * @default 2
   */
  backoffMultiplier?: number
  /**
   * HTTP status codes that should trigger retry
   * @default [408, 429, 500, 502, 503, 504]
   */
  retryableStatusCodes?: number[]
  /**
   * Whether to retry on network errors
   * @default true
   */
  retryOnNetworkError?: boolean
}

/**
 * Extended fetch request config with our custom properties
 */
export interface ExtendedFetchRequestInit extends RequestInit {
  retry?: RetryConfig | boolean
  skipAuth?: boolean
  skipTenantId?: boolean
  requestId?: string
  skipRetry?: boolean
  _retryCount?: number
  _retryDelay?: number
  baseURL?: string
  timeout?: number
  // Query parameters (for GET requests)
  params?: Record<string, any>
}

/**
 * API error response structure
 * Matches the backend error format
 */
export interface ApiErrorResponse {
  error: {
    /**
     * Error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
     */
    code: string
    /**
     * Human-readable error message
     */
    message: string
    /**
     * HTTP status code
     */
    http_status?: number
    /**
     * Request ID for tracing
     */
    request_id?: string
    /**
     * Error timestamp
     */
    timestamp?: string
    /**
     * Additional error details
     */
    details?: {
      /**
       * Field-specific validation errors
       */
      field_errors?: Array<{
        field: string
        message: string
        code: string
      }>
      /**
       * Additional error context
       */
      [key: string]: any
    }
  }
}

/**
 * Rate limit response headers
 */
export interface RateLimitHeaders {
  'x-ratelimit-limit'?: string
  'x-ratelimit-remaining'?: string
  'x-ratelimit-reset'?: string
  'retry-after'?: string
}
