/**
 * createTestQueryClient Utility
 *
 * Creates a QueryClient instance optimized for testing:
 * - No retries (faster test execution)
 * - No caching (fresh state for each test)
 * - Configurable options for different test scenarios
 */

import { QueryClient, QueryClientConfig } from '@tanstack/react-query'

/**
 * Options for creating a test QueryClient
 */
export interface CreateTestQueryClientOptions {
  /**
   * Enable retries in tests
   * @default false
   */
  retry?: boolean
  /**
   * Garbage collection time in milliseconds
   * @default 0 (no caching)
   */
  gcTime?: number
  /**
   * Stale time in milliseconds
   * @default 0 (always stale)
   */
  staleTime?: number
  /**
   * Refetch on window focus
   * @default false
   */
  refetchOnWindowFocus?: boolean
  /**
   * Refetch on reconnect
   * @default false
   */
  refetchOnReconnect?: boolean
  /**
   * Refetch on mount
   * @default false
   */
  refetchOnMount?: boolean
  /**
   * Additional QueryClient options
   */
  additionalOptions?: Partial<QueryClientConfig>
}

/**
 * Create a QueryClient instance optimized for testing
 *
 * @param options - QueryClient configuration options
 * @returns Configured QueryClient instance
 *
 * @example
 * ```tsx
 * import { createTestQueryClient } from '@/test-utils'
 *
 * const queryClient = createTestQueryClient()
 * ```
 *
 * @example
 * ```tsx
 * // With custom options
 * const queryClient = createTestQueryClient({
 *   retry: true,
 *   gcTime: 1000,
 * })
 * ```
 */
export function createTestQueryClient(
  options: CreateTestQueryClientOptions = {}
): QueryClient {
  const {
    retry = false,
    gcTime = 0,
    staleTime = 0,
    refetchOnWindowFocus = false,
    refetchOnReconnect = false,
    refetchOnMount = false,
    additionalOptions = {},
  } = options

  return new QueryClient({
    defaultOptions: {
      queries: {
        retry,
        gcTime,
        staleTime,
        refetchOnWindowFocus,
        refetchOnReconnect,
        refetchOnMount,
      },
      mutations: {
        retry,
        gcTime,
      },
    },
    logger: {
      log: () => {},
      warn: () => {},
      error: () => {},
    },
    ...additionalOptions,
  })
}

/**
 * Create a QueryClient with caching enabled (useful for integration tests)
 *
 * @param options - QueryClient configuration options
 * @returns Configured QueryClient instance with caching
 */
export function createTestQueryClientWithCache(
  options: CreateTestQueryClientOptions = {}
): QueryClient {
  return createTestQueryClient({
    gcTime: 5 * 60 * 1000, // 5 minutes
    staleTime: 0,
    ...options,
  })
}

