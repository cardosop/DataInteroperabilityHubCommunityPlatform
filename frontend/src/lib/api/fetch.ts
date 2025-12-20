/**
 * Fetch-based API Client
 *
 * Comprehensive fetch-based HTTP client with interceptors, retry logic, and error handling.
 * Replaces axios to avoid CommonJS/ESM interop issues with Vite pre-bundling.
 */

import { config } from '@/lib/config'
// Lazy import auth functions to avoid circular dependency
// auth.ts imports client.ts which imports fetch.ts
import type {
  RateLimitHandler,
  RequestIdGenerator,
  TenantIdGetter,
  TokenRefreshFunction,
} from './types'
import { generateRequestId } from './utils/requestId'
import { delay, getRetryDelay, shouldRetry } from './utils/retry'

/**
 * Configuration for API client
 */
export interface ApiClientOptions {
  /**
   * Base URL override (defaults to config.api.baseUrl)
   */
  baseURL?: string
  /**
   * Timeout in milliseconds (defaults to config.api.timeout)
   */
  timeout?: number
  /**
   * Custom request ID generator
   */
  requestIdGenerator?: RequestIdGenerator
  /**
   * Custom tenant ID getter
   */
  tenantIdGetter?: TenantIdGetter
  /**
   * Token refresh function
   */
  tokenRefresh?: TokenRefreshFunction
  /**
   * Rate limit handler
   */
  rateLimitHandler?: RateLimitHandler
  /**
   * Whether to enable request logging (defaults to config.development.enableApiLogging)
   */
  enableLogging?: boolean
}

/**
 * Extended fetch request options
 */
export interface ExtendedFetchRequestInit extends RequestInit {
  requestId?: string
  skipAuth?: boolean
  skipTenantId?: boolean
  _retry?: boolean
  _retryCount?: number
  _retryDelay?: number
  baseURL?: string
  timeout?: number
}

/**
 * Fetch response wrapper to match axios-like interface
 */
export interface FetchResponse<T = any> {
  data: T
  status: number
  statusText: string
  headers: Headers
  config: ExtendedFetchRequestInit
  request?: Request
}

/**
 * Fetch error class to match axios-like interface
 */
export class FetchError extends Error {
  response?: FetchResponse
  request?: Request
  config?: ExtendedFetchRequestInit
  code?: string

  constructor(
    message: string,
    config?: ExtendedFetchRequestInit,
    request?: Request,
    response?: FetchResponse
  ) {
    super(message)
    this.name = 'FetchError'
    this.config = config
    this.request = request
    this.response = response
    this.code = response?.status?.toString()
  }
}

/**
 * Create a fetch-based API client
 */
export function createFetchClient(options: ApiClientOptions = {}) {
  const {
    baseURL = config.api.baseUrl,
    timeout = config.api.timeout,
    requestIdGenerator = generateRequestId, // Lazy evaluation - function reference, not called
    tenantIdGetter = () => {
      // Get tenant ID from localStorage or user context
      if (typeof window === 'undefined') return null
      const userStr = localStorage.getItem('auth_user')
      if (!userStr) return null
      try {
        const user = JSON.parse(userStr)
        return user.tenantId || null
      } catch {
        return null
      }
    },
    tokenRefresh,
    rateLimitHandler,
    enableLogging = config.development.enableApiLogging,
  } = options

  /**
   * Create abort controller for timeout
   */
  function createTimeoutController(timeoutMs: number): AbortController {
    const controller = new AbortController()
    setTimeout(() => controller.abort(), timeoutMs)
    return controller
  }

  /**
   * Build full URL with query parameters
   */
  function buildURL(url: string, base?: string, params?: Record<string, any>): string {
    let fullURL: string
    if (url.startsWith('http://') || url.startsWith('https://')) {
      fullURL = url
    } else {
      const baseUrl = base || baseURL
      fullURL = `${baseUrl.replace(/\/$/, '')}/${url.replace(/^\//, '')}`
    }

    // Add query parameters
    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          if (Array.isArray(value)) {
            value.forEach(v => searchParams.append(key, String(v)))
          } else {
            searchParams.set(key, String(value))
          }
        }
      })
      const queryString = searchParams.toString()
      if (queryString) {
        fullURL += (fullURL.includes('?') ? '&' : '?') + queryString
      }
    }

    return fullURL
  }

  /**
   * Build headers with auth and tenant ID
   * Made async to support lazy auth import (avoids circular dependency)
   */
  async function buildHeaders(
    init: ExtendedFetchRequestInit,
    skipAuth = false,
    skipTenantId = false
  ): Promise<Headers> {
    const headers = new Headers(init.headers)

    // Set default content type for JSON requests
    if (!headers.has('Content-Type') && init.body) {
      headers.set('Content-Type', 'application/json')
    }
    if (!headers.has('Accept')) {
      headers.set('Accept', 'application/json')
    }

    // Add request ID
    if (init.requestId) {
      headers.set('X-Request-ID', init.requestId)
    }

    // Add authentication token (lazy import to avoid circular dependency)
    if (!skipAuth) {
      const { getAuthToken } = await import('./auth')
      const token = getAuthToken()
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
    }

    // Add tenant ID
    if (!skipTenantId) {
      const tenantId = tenantIdGetter()
      if (tenantId) {
        headers.set('X-Tenant-ID', tenantId)
      }
    }

    return headers
  }

  /**
   * Parse response body
   */
  async function parseResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get('content-type')
    if (contentType?.includes('application/json')) {
      return response.json()
    }
    const text = await response.text()
    try {
      return JSON.parse(text) as T
    } catch {
      return text as unknown as T
    }
  }

  /**
   * Create fetch response wrapper
   */
  function createResponse<T>(
    response: Response,
    data: T,
    config: ExtendedFetchRequestInit,
    request?: Request
  ): FetchResponse<T> {
    return {
      data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
      config,
      request,
    }
  }

  /**
   * Main fetch function with interceptors and retry logic
   */
  async function fetchWithInterceptors<T = any>(
    url: string,
    init: ExtendedFetchRequestInit = {}
  ): Promise<FetchResponse<T>> {
    const extendedInit: ExtendedFetchRequestInit = {
      ...init,
      baseURL: init.baseURL || baseURL,
      timeout: init.timeout || timeout,
    }

    // Generate request ID if not provided
    if (!extendedInit.requestId && !extendedInit.skipAuth) {
      extendedInit.requestId = requestIdGenerator()
    }

    // Build headers (async due to lazy auth import)
    const headers = await buildHeaders(
      extendedInit,
      extendedInit.skipAuth,
      extendedInit.skipTenantId
    )

    // Extract query params from config if present (for GET requests)
    const params = (extendedInit as any).params

    // Build full URL with query parameters
    const fullURL = buildURL(url, extendedInit.baseURL, params)

    // Logging
    if (enableLogging) {
      console.log('[API Request]', {
        method: (init.method || 'GET').toUpperCase(),
        url: fullURL,
        baseURL: extendedInit.baseURL,
        requestId: extendedInit.requestId,
        headers: Object.fromEntries(headers.entries()),
      })
    }

    // Create timeout controller
    const timeoutController = createTimeoutController(extendedInit.timeout || timeout)

    // Combine abort signals
    const abortController = new AbortController()
    if (init.signal) {
      init.signal.addEventListener('abort', () => abortController.abort())
    }
    timeoutController.signal.addEventListener('abort', () => abortController.abort())

    // Make request
    let request: Request
    let response: Response

    try {
      request = new Request(fullURL, {
        ...extendedInit,
        headers,
        signal: abortController.signal,
      })

      response = await fetch(request)
    } catch (error: any) {
      // Handle network errors
      if (error.name === 'AbortError') {
        throw new FetchError(
          `Request timeout after ${extendedInit.timeout || timeout}ms`,
          extendedInit,
          request!
        )
      }
      throw new FetchError(
        error.message || 'Network error',
        extendedInit,
        request!
      )
    }

    // Parse response
    const data = await parseResponse<T>(response)

    // Handle rate limiting headers
    if (rateLimitHandler && response.headers.has('retry-after')) {
      const retryAfter = response.headers.get('retry-after')
      if (retryAfter) {
        const retryAfterSeconds = parseInt(retryAfter, 10)
        if (!isNaN(retryAfterSeconds)) {
          rateLimitHandler(retryAfterSeconds)
        }
      }
    }

    // Logging
    if (enableLogging) {
      console.log('[API Response]', {
        method: (init.method || 'GET').toUpperCase(),
        url: fullURL,
        status: response.status,
        requestId: extendedInit.requestId,
      })
    }

    // Handle non-2xx responses
    if (!response.ok) {
      const fetchResponse = createResponse(response, data, extendedInit, request)

      // Handle 401 Unauthorized - Token refresh or logout
      if (response.status === 401 && !extendedInit._retry) {
        extendedInit._retry = true

        // Try to refresh token if refresh function is provided
        if (tokenRefresh) {
          try {
            const newToken = await tokenRefresh()
            if (newToken) {
              // Retry with new token
              extendedInit._retry = false
              headers.set('Authorization', `Bearer ${newToken}`)
              return fetchWithInterceptors<T>(url, {
                ...extendedInit,
                headers,
              })
            }
          } catch (refreshError) {
            // Token refresh failed, clear auth and redirect to login (lazy import to avoid circular dependency)
            const { clearAuthTokens } = await import('./auth')
            clearAuthTokens()
            if (typeof window !== 'undefined') {
              window.location.href = '/login'
            }
            throw new FetchError(
              'Token refresh failed',
              extendedInit,
              request,
              fetchResponse
            )
          }
        }

        // No refresh function or refresh failed, clear auth and redirect (lazy import to avoid circular dependency)
        const { clearAuthTokens } = await import('./auth')
        clearAuthTokens()
        if (typeof window !== 'undefined') {
          window.location.href = '/login'
        }
      }

      // Handle 429 Rate Limit
      if (response.status === 429) {
        const retryAfter = response.headers.get('retry-after')
        if (retryAfter && rateLimitHandler) {
          const retryAfterSeconds = parseInt(retryAfter, 10)
          if (!isNaN(retryAfterSeconds)) {
            rateLimitHandler(retryAfterSeconds)
          }
        }
      }

      // Retry logic with exponential backoff
      const error = new FetchError(
        `Request failed with status ${response.status}`,
        extendedInit,
        request,
        fetchResponse
      )

      if (shouldRetry(error, extendedInit)) {
        const retryCount = (extendedInit._retryCount || 0) + 1
        extendedInit._retryCount = retryCount

        // Check for Retry-After header for rate limiting
        let retryDelay = getRetryDelay(extendedInit)
        if (response.headers.has('retry-after')) {
          const retryAfter = parseInt(response.headers.get('retry-after')!, 10)
          if (!isNaN(retryAfter)) {
            retryDelay = retryAfter * 1000 // Convert to milliseconds
          }
        }
        extendedInit._retryDelay = retryDelay

        // Wait before retrying
        await delay(retryDelay)

        if (enableLogging) {
          console.log('[API Retry]', {
            attempt: retryCount,
            delay: retryDelay,
            url: fullURL,
            status: response.status,
          })
        }

        return fetchWithInterceptors<T>(url, extendedInit)
      }

      throw error
    }

    return createResponse<T>(response, data, extendedInit, request)
  }

  // Return axios-like interface
  return {
    get: <T = any>(url: string, config?: ExtendedFetchRequestInit) =>
      fetchWithInterceptors<T>(url, { ...config, method: 'GET' }),
    post: <T = any>(url: string, data?: any, config?: ExtendedFetchRequestInit) =>
      fetchWithInterceptors<T>(url, {
        ...config,
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
      }),
    put: <T = any>(url: string, data?: any, config?: ExtendedFetchRequestInit) =>
      fetchWithInterceptors<T>(url, {
        ...config,
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined,
      }),
    patch: <T = any>(url: string, data?: any, config?: ExtendedFetchRequestInit) =>
      fetchWithInterceptors<T>(url, {
        ...config,
        method: 'PATCH',
        body: data ? JSON.stringify(data) : undefined,
      }),
    delete: <T = any>(url: string, config?: ExtendedFetchRequestInit) =>
      fetchWithInterceptors<T>(url, { ...config, method: 'DELETE' }),
    request: <T = any>(config: ExtendedFetchRequestInit & { url: string }) => {
      const { url, ...rest } = config
      return fetchWithInterceptors<T>(url, rest)
    },
  }
}

/**
 * Default fetch client instance
 */
export const apiClient = createFetchClient()

export default apiClient

