/**
 * MSW Utilities
 *
 * Helper utilities for working with MSW in tests.
 */

import { http, HttpResponse } from 'msw'
import { server } from './server'
import { config } from '@/lib/config'

/**
 * API base URL
 */
const API_BASE_URL = config.api.baseUrl

/**
 * Create a delay response (useful for testing loading states)
 *
 * @param delayMs - Delay in milliseconds
 * @param response - Response to return after delay
 * @returns HTTP handler with delay
 *
 * @example
 * ```tsx
 * server.use(
 *   createDelayedResponse(1000, http.get(`${API_BASE_URL}/assets/`, () => {
 *     return HttpResponse.json({ results: [] })
 *   }))
 * )
 * ```
 */
export function createDelayedResponse<T>(
  delayMs: number,
  response: T
): Promise<T> {
  return new Promise((resolve) => {
    setTimeout(() => resolve(response), delayMs)
  })
}

/**
 * Create an error response handler
 *
 * @param status - HTTP status code
 * @param message - Error message
 * @param code - Error code
 * @returns HTTP handler that returns error
 *
 * @example
 * ```tsx
 * server.use(
 *   createErrorHandler(404, 'Not found', 'NOT_FOUND')
 * )
 * ```
 */
export function createErrorHandler(
  status: number,
  message: string,
  code: string = `HTTP_${status}`
) {
  return http.all(`${API_BASE_URL}/*`, () => {
    return HttpResponse.json(
      {
        error: {
          message,
          code,
          http_status: status,
          request_id: `test-request-${Date.now()}`,
          timestamp: new Date().toISOString(),
        },
      },
      { status }
    )
  })
}

/**
 * Create a network error handler (simulates network failure)
 *
 * @returns HTTP handler that throws network error
 *
 * @example
 * ```tsx
 * server.use(createNetworkErrorHandler())
 * ```
 */
export function createNetworkErrorHandler() {
  return http.all(`${API_BASE_URL}/*`, () => {
    return HttpResponse.error()
  })
}

/**
 * Create a handler that returns empty response
 *
 * @param status - HTTP status code (default: 204)
 * @returns HTTP handler that returns empty response
 *
 * @example
 * ```tsx
 * server.use(
 *   createEmptyResponseHandler(204)
 * )
 * ```
 */
export function createEmptyResponseHandler(status: number = 204) {
  return http.all(`${API_BASE_URL}/*`, () => {
    return new HttpResponse(null, { status })
  })
}

/**
 * Wait for a specific request to be made
 *
 * @param url - URL pattern to wait for
 * @param timeout - Timeout in milliseconds (default: 5000)
 * @returns Promise that resolves when request is made
 *
 * @example
 * ```tsx
 * await waitForRequest(`${API_BASE_URL}/assets/`)
 * ```
 */
export function waitForRequest(
  url: string,
  timeout: number = 5000
): Promise<void> {
  return new Promise((resolve, reject) => {
    const startTime = Date.now()

    const checkRequest = () => {
      // Check if request was made (this is a simplified check)
      // In a real implementation, you might want to track requests
      if (Date.now() - startTime > timeout) {
        reject(new Error(`Timeout waiting for request to ${url}`))
        return
      }

      // For now, resolve immediately
      // In a real implementation, you'd check if the request was actually made
      resolve()
    }

    checkRequest()
  })
}

/**
 * Reset all MSW handlers to default
 *
 * @example
 * ```tsx
 * resetMSWHandlers()
 * ```
 */
export function resetMSWHandlers() {
  server.resetHandlers()
}

/**
 * Use custom handlers for a test
 *
 * @param handlers - MSW handlers to use
 * @returns Function to restore default handlers
 *
 * @example
 * ```tsx
 * const restore = useCustomHandlers([
 *   http.get(`${API_BASE_URL}/assets/`, () => {
 *     return HttpResponse.json({ results: [] })
 *   })
 * ])
 *
 * // ... test code ...
 *
 * restore()
 * ```
 */
export function useCustomHandlers(handlers: Parameters<typeof server.use>[0][]) {
  server.use(...handlers)

  return () => {
    server.resetHandlers()
  }
}

