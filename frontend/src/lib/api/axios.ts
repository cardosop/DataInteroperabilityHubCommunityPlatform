/**
 * Axios Instance Configuration
 *
 * Comprehensive Axios instance with interceptors, retry logic, and error handling.
 */

import { config } from '@/lib/config'
import type { AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import axios, { AxiosError } from 'axios'
import { clearAuthTokens, getAuthToken } from './auth'
import type {
  ExtendedAxiosRequestConfig,
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
 * Create configured Axios instance
 */
export function createAxiosInstance(options: ApiClientOptions = {}): AxiosInstance {
  const {
    baseURL = config.api.baseUrl,
    timeout = config.api.timeout,
    requestIdGenerator = generateRequestId,
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

  // Create Axios instance
  const instance = axios.create({
    baseURL,
    timeout,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
  })

  // Request interceptor
  instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const extendedConfig = config as ExtendedAxiosRequestConfig

      // Generate request ID if not provided
      if (!extendedConfig.requestId && !extendedConfig.skipAuth) {
        extendedConfig.requestId = requestIdGenerator()
      }

      // Add request ID header
      if (extendedConfig.requestId && config.headers) {
        config.headers['X-Request-ID'] = extendedConfig.requestId
      }

      // Add authentication token
      if (!extendedConfig.skipAuth && config.headers) {
        const token = getAuthToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
      }

      // Add tenant ID
      if (!extendedConfig.skipTenantId && config.headers) {
        const tenantId = tenantIdGetter()
        if (tenantId) {
          config.headers['X-Tenant-ID'] = tenantId
        }
      }

      // Logging
      if (enableLogging) {
        console.log('[API Request]', {
          method: config.method?.toUpperCase(),
          url: config.url,
          baseURL: config.baseURL,
          requestId: extendedConfig.requestId,
          headers: {
            ...config.headers,
            Authorization: config.headers.Authorization ? '[REDACTED]' : undefined,
          },
        })
      }

      return config
    },
    (error: AxiosError) => {
      if (enableLogging) {
        console.error('[API Request Error]', error)
      }
      return Promise.reject(error)
    }
  )

  // Response interceptor
  instance.interceptors.response.use(
    (response: AxiosResponse) => {
      const extendedConfig = response.config as ExtendedAxiosRequestConfig

      // Handle rate limiting headers
      if (rateLimitHandler && response.headers) {
        const retryAfter = response.headers['retry-after']
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
          method: response.config.method?.toUpperCase(),
          url: response.config.url,
          status: response.status,
          requestId: extendedConfig.requestId,
        })
      }

      return response
    },
    async (error: AxiosError) => {
      const originalRequest = error.config as ExtendedAxiosRequestConfig

      // Logging
      if (enableLogging) {
        console.error('[API Response Error]', {
          method: originalRequest?.method?.toUpperCase(),
          url: originalRequest?.url,
          status: error.response?.status,
          requestId: originalRequest?.requestId,
          error: error.message,
        })
      }

      // Handle 401 Unauthorized - Token refresh or logout
      // Don't retry 401 errors automatically
      if (error.response?.status === 401 && originalRequest) {
        // Mark as retried to prevent infinite loops
        if (!originalRequest._retry) {
          originalRequest._retry = true

          // Try to refresh token if refresh function is provided
          if (tokenRefresh) {
            try {
              const newToken = await tokenRefresh()
              if (newToken && originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                // Reset retry flag for the retry attempt
                originalRequest._retry = false
                return instance(originalRequest)
              }
            } catch (refreshError) {
              // Token refresh failed, clear auth and redirect to login
              clearAuthTokens()
              if (typeof window !== 'undefined') {
                window.location.href = '/login'
              }
              return Promise.reject(refreshError)
            }
          }

          // No refresh function or refresh failed, clear auth and redirect
          clearAuthTokens()
          if (typeof window !== 'undefined') {
            window.location.href = '/login'
          }
        }

        // Don't retry 401 errors
        return Promise.reject(error)
      }

      // Handle 429 Rate Limit
      if (error.response?.status === 429) {
        const retryAfter = error.response.headers['retry-after']
        if (retryAfter && rateLimitHandler) {
          const retryAfterSeconds = parseInt(retryAfter, 10)
          if (!isNaN(retryAfterSeconds)) {
            rateLimitHandler(retryAfterSeconds)
          }
        }
      }

      // Retry logic with exponential backoff
      if (shouldRetry(error, originalRequest)) {
        const retryCount = (originalRequest._retryCount || 0) + 1
        originalRequest._retryCount = retryCount

        // Check for Retry-After header for rate limiting
        let retryDelay = getRetryDelay(originalRequest)
        if (error.response?.headers?.['retry-after']) {
          const retryAfter = parseInt(error.response.headers['retry-after'], 10)
          if (!isNaN(retryAfter)) {
            retryDelay = retryAfter * 1000 // Convert to milliseconds
          }
        }
        originalRequest._retryDelay = retryDelay

        // Wait before retrying
        await delay(retryDelay)

        if (enableLogging) {
          console.log('[API Retry]', {
            attempt: retryCount,
            delay: retryDelay,
            url: originalRequest.url,
            status: error.response?.status,
          })
        }

        return instance(originalRequest)
      }

      return Promise.reject(error)
    }
  )

  return instance
}

/**
 * Default Axios instance
 */
export const apiClient = createAxiosInstance()

export default apiClient
