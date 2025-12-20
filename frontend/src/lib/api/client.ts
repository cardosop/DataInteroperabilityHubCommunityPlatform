/**
 * API Client Factory
 *
 * Factory for creating configured API clients with different configurations.
 */

import { createFetchClient } from './fetch'
import type { ApiClientOptions } from './fetch'
import { config } from '@/lib/config'
// Lazy import to avoid circular dependency with auth.ts

/**
 * API client type (return type of createFetchClient)
 */
export type ApiClient = ReturnType<typeof createFetchClient>

/**
 * API client instances cache
 */
const clientCache = new Map<string, ApiClient>()

/**
 * Create or get a cached API client instance
 */
export function createApiClient(
  name: string = 'default',
  options?: ApiClientOptions
): ApiClient {
  // Return cached instance if exists and no options provided
  if (clientCache.has(name) && !options) {
    return clientCache.get(name)!
  }

  // Create new instance
  const instance = createFetchClient(options)

  // Cache it
  clientCache.set(name, instance)

  return instance
}

/**
 * Get a cached API client instance
 */
export function getApiClient(name: string = 'default'): ApiClient {
  if (!clientCache.has(name)) {
    return createApiClient(name)
  }
  return clientCache.get(name)!
}

/**
 * Remove a cached API client instance
 */
export function removeApiClient(name: string): boolean {
  return clientCache.delete(name)
}

/**
 * Clear all cached API client instances
 */
export function clearApiClients(): void {
  clientCache.clear()
}

/**
 * Default API client (singleton)
 * Configured with automatic token refresh using the auth service
 * Uses lazy import to avoid circular dependency
 */
export const apiClient = createApiClient('default', {
  baseURL: config.api.baseUrl,
  timeout: config.api.timeout,
  enableLogging: config.development.enableApiLogging,
  tokenRefresh: async () => {
    try {
      // Lazy import to avoid circular dependency
      const { refreshAuthToken } = await import('./auth')
      return await refreshAuthToken()
    } catch {
      return null
    }
  },
})

/**
 * Public API client for external use
 * This is the main export for API calls
 */
export { apiClient as default }

/**
 * Create a public API client (no auth, no tenant ID)
 */
export function createPublicApiClient(options?: Omit<ApiClientOptions, 'skipAuth' | 'skipTenantId'>): ApiClient {
  return createFetchClient({
    ...options,
    // Public clients skip auth and tenant ID by default
    // Individual requests can override this
  })
}

/**
 * Create an authenticated API client with custom configuration
 */
export function createAuthenticatedApiClient(
  token: string,
  options?: ApiClientOptions
): ApiClient {
  // For fetch, we'll pass the token via a custom header function
  // This is simpler than interceptors
  const client = createFetchClient(options)

  // Wrap the client methods to inject the token
  const originalGet = client.get
  const originalPost = client.post
  const originalPut = client.put
  const originalPatch = client.patch
  const originalDelete = client.delete
  const originalRequest = client.request

  return {
    ...client,
    get: (url, config) => originalGet(url, { ...config, headers: { ...config?.headers, Authorization: `Bearer ${token}` } }),
    post: (url, data, config) => originalPost(url, data, { ...config, headers: { ...config?.headers, Authorization: `Bearer ${token}` } }),
    put: (url, data, config) => originalPut(url, data, { ...config, headers: { ...config?.headers, Authorization: `Bearer ${token}` } }),
    patch: (url, data, config) => originalPatch(url, data, { ...config, headers: { ...config?.headers, Authorization: `Bearer ${token}` } }),
    delete: (url, config) => originalDelete(url, { ...config, headers: { ...config?.headers, Authorization: `Bearer ${token}` } }),
    request: (config) => originalRequest({ ...config, headers: { ...config.headers, Authorization: `Bearer ${token}` } }),
  }
}

