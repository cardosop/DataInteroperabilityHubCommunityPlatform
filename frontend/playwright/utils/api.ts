/**
 * API Helpers for Playwright Tests
 *
 * Comprehensive API utilities for E2E tests.
 * Provides helpers for making API calls, handling responses, and managing API state.
 *
 * Uses real API calls - no mocks/stubs. Always fixes root cause.
 */

import { Page, APIRequestContext, expect } from '@playwright/test'
import type { AxiosRequestConfig } from 'axios'

/**
 * API response wrapper
 */
export interface ApiResponse<T = any> {
  data: T
  status: number
  statusText: string
  headers: Record<string, string>
}

/**
 * API error response
 */
export interface ApiError {
  message: string
  code?: string
  status: number
  details?: Record<string, any>
}

/**
 * Get API base URL from environment or default
 */
export function getApiBaseUrl(): string {
  return process.env.VITE_API_BASE_URL || process.env.PLAYWRIGHT_API_BASE_URL || 'http://localhost:8000'
}

/**
 * Create API request context with authentication
 *
 * Note: Playwright's APIRequestContext is created from BrowserContext, not Page.
 * This function returns the page's request context with authentication headers set.
 *
 * @param page - Playwright page instance (for getting auth token)
 * @param baseURL - Optional base URL override
 * @returns API request context (page.request with auth headers)
 *
 * @example
 * ```ts
 * const apiContext = createApiContext(page)
 * ```
 */
export function createApiContext(page: Page, baseURL?: string): APIRequestContext {
  // Return page.request - it already has the context
  // Authentication headers will be set per-request via authenticatedApiRequest
  return page.request
}

/**
 * Make GET request
 *
 * @param context - API request context or page
 * @param url - Endpoint URL (relative to base URL)
 * @param options - Request options
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await apiGet(page, '/api/v1/assets/')
 * ```
 */
export async function apiGet<T = any>(
  context: Page | APIRequestContext,
  url: string,
  options: {
    headers?: Record<string, string>
    params?: Record<string, string | number | boolean>
  } = {}
): Promise<ApiResponse<T>> {
  const requestContext = 'request' in context ? context.request : context

  // Build URL with query parameters
  const urlObj = new URL(url, getApiBaseUrl())
  if (options.params) {
    Object.entries(options.params).forEach(([key, value]) => {
      urlObj.searchParams.append(key, String(value))
    })
  }

  const response = await requestContext.get(urlObj.pathname + urlObj.search, {
    headers: options.headers,
  })

  const data = await response.json().catch(() => null)

  return {
    data: data as T,
    status: response.status(),
    statusText: response.statusText(),
    headers: response.headers(),
  }
}

/**
 * Make POST request
 *
 * @param context - API request context or page
 * @param url - Endpoint URL (relative to base URL)
 * @param data - Request body
 * @param options - Request options
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await apiPost(page, '/api/v1/assets/', { name: 'Test Asset' })
 * ```
 */
export async function apiPost<T = any>(
  context: Page | APIRequestContext,
  url: string,
  data?: any,
  options: {
    headers?: Record<string, string>
  } = {}
): Promise<ApiResponse<T>> {
  const requestContext = 'request' in context ? context.request : context

  const response = await requestContext.post(url, {
    data,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const responseData = await response.json().catch(() => null)

  return {
    data: responseData as T,
    status: response.status(),
    statusText: response.statusText(),
    headers: response.headers(),
  }
}

/**
 * Make PUT request
 *
 * @param context - API request context or page
 * @param url - Endpoint URL (relative to base URL)
 * @param data - Request body
 * @param options - Request options
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await apiPut(page, '/api/v1/assets/123', { name: 'Updated Asset' })
 * ```
 */
export async function apiPut<T = any>(
  context: Page | APIRequestContext,
  url: string,
  data?: any,
  options: {
    headers?: Record<string, string>
  } = {}
): Promise<ApiResponse<T>> {
  const requestContext = 'request' in context ? context.request : context

  const response = await requestContext.put(url, {
    data,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const responseData = await response.json().catch(() => null)

  return {
    data: responseData as T,
    status: response.status(),
    statusText: response.statusText(),
    headers: response.headers(),
  }
}

/**
 * Make PATCH request
 *
 * @param context - API request context or page
 * @param url - Endpoint URL (relative to base URL)
 * @param data - Request body
 * @param options - Request options
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await apiPatch(page, '/api/v1/assets/123', { name: 'Updated Asset' })
 * ```
 */
export async function apiPatch<T = any>(
  context: Page | APIRequestContext,
  url: string,
  data?: any,
  options: {
    headers?: Record<string, string>
  } = {}
): Promise<ApiResponse<T>> {
  const requestContext = 'request' in context ? context.request : context

  const response = await requestContext.patch(url, {
    data,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const responseData = await response.json().catch(() => null)

  return {
    data: responseData as T,
    status: response.status(),
    statusText: response.statusText(),
    headers: response.headers(),
  }
}

/**
 * Make DELETE request
 *
 * @param context - API request context or page
 * @param url - Endpoint URL (relative to base URL)
 * @param options - Request options
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await apiDelete(page, '/api/v1/assets/123')
 * ```
 */
export async function apiDelete<T = any>(
  context: Page | APIRequestContext,
  url: string,
  options: {
    headers?: Record<string, string>
  } = {}
): Promise<ApiResponse<T>> {
  const requestContext = 'request' in context ? context.request : context

  const response = await requestContext.delete(url, {
    headers: options.headers,
  })

  const responseData = await response.json().catch(() => null)

  return {
    data: responseData as T,
    status: response.status(),
    statusText: response.statusText(),
    headers: response.headers(),
  }
}

/**
 * Handle API error response
 *
 * @param response - API response
 * @returns API error object
 *
 * @example
 * ```ts
 * try {
 *   await apiPost(page, '/api/v1/assets/', data)
 * } catch (error) {
 *   const apiError = handleApiError(error)
 *   console.error(apiError.message)
 * }
 * ```
 */
export function handleApiError(response: ApiResponse): ApiError {
  const errorData = response.data?.error || response.data

  return {
    message: errorData?.message || `API request failed with status ${response.status}`,
    code: errorData?.code,
    status: response.status,
    details: errorData?.details,
  }
}

/**
 * Assert API response is successful
 *
 * @param response - API response
 * @param expectedStatus - Expected status code (default: 200)
 *
 * @example
 * ```ts
 * const response = await apiGet(page, '/api/v1/assets/')
 * assertApiSuccess(response, 200)
 * ```
 */
export function assertApiSuccess(response: ApiResponse, expectedStatus: number = 200): void {
  expect(response.status).toBe(expectedStatus)
  expect(response.data).toBeDefined()
}

/**
 * Assert API response is an error
 *
 * @param response - API response
 * @param expectedStatus - Expected error status code
 *
 * @example
 * ```ts
 * const response = await apiGet(page, '/api/v1/assets/999')
 * assertApiError(response, 404)
 * ```
 */
export function assertApiError(response: ApiResponse, expectedStatus: number): void {
  expect(response.status).toBe(expectedStatus)
  expect(response.data?.error || response.data).toBeDefined()
}

/**
 * Wait for API endpoint to be available
 *
 * @param context - API request context or page
 * @param url - Endpoint URL
 * @param timeout - Maximum time to wait in milliseconds
 * @param interval - Check interval in milliseconds
 *
 * @example
 * ```ts
 * await waitForApiEndpoint(page, '/api/v1/health/', 30000)
 * ```
 */
export async function waitForApiEndpoint(
  context: Page | APIRequestContext,
  url: string,
  timeout: number = 30000,
  interval: number = 1000
): Promise<void> {
  const requestContext = 'request' in context ? context.request : context
  const startTime = Date.now()

  while (Date.now() - startTime < timeout) {
    try {
      const response = await requestContext.get(url, { timeout: 5000 })
      if (response.ok()) {
        return
      }
    } catch (error) {
      // Continue waiting
    }

    await new Promise((resolve) => setTimeout(resolve, interval))
  }

  throw new Error(`API endpoint ${url} not available after ${timeout}ms`)
}

/**
 * Retry API request with exponential backoff
 *
 * @param fn - Function that makes API request
 * @param maxRetries - Maximum number of retries
 * @param initialDelay - Initial delay in milliseconds
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await retryApiRequest(
 *   () => apiGet(page, '/api/v1/assets/'),
 *   3,
 *   1000
 * )
 * ```
 */
export async function retryApiRequest<T>(
  fn: () => Promise<ApiResponse<T>>,
  maxRetries: number = 3,
  initialDelay: number = 1000
): Promise<ApiResponse<T>> {
  let lastError: Error | null = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fn()
      if (response.status < 500) {
        // Don't retry client errors (4xx)
        return response
      }
      if (attempt === maxRetries) {
        return response
      }
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))
      if (attempt === maxRetries) {
        throw lastError
      }
    }

    // Exponential backoff
    const delay = initialDelay * Math.pow(2, attempt)
    await new Promise((resolve) => setTimeout(resolve, delay))
  }

  throw lastError || new Error('API request failed after retries')
}

/**
 * Make authenticated API request (automatically includes auth token)
 *
 * @param page - Playwright page instance
 * @param method - HTTP method
 * @param url - Endpoint URL
 * @param data - Request body (for POST/PUT/PATCH)
 * @param options - Request options
 * @returns API response
 *
 * @example
 * ```ts
 * const response = await authenticatedApiRequest(page, 'GET', '/api/v1/assets/')
 * ```
 */
export async function authenticatedApiRequest<T = any>(
  page: Page,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  url: string,
  data?: any,
  options: {
    headers?: Record<string, string>
    params?: Record<string, string | number | boolean>
  } = {}
): Promise<ApiResponse<T>> {
  // Get auth token from page
  const authToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!authToken) {
    throw new Error('No authentication token available')
  }

  const headers = {
    Authorization: `Bearer ${authToken}`,
    'Content-Type': 'application/json',
    ...options.headers,
  }

  switch (method) {
    case 'GET':
      return apiGet(page, url, { ...options, headers })
    case 'POST':
      return apiPost(page, url, data, { headers })
    case 'PUT':
      return apiPut(page, url, data, { headers })
    case 'PATCH':
      return apiPatch(page, url, data, { headers })
    case 'DELETE':
      return apiDelete(page, url, { headers })
    default:
      throw new Error(`Unsupported HTTP method: ${method}`)
  }
}

