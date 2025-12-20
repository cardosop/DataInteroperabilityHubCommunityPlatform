/**
 * React Query (TanStack Query) Configuration
 *
 * Comprehensive React Query setup with:
 * - QueryClient configuration
 * - Default query and mutation options
 * - Query key factories for consistent key management
 * - Error handling
 * - DevTools integration
 */

import { QueryClient } from '@tanstack/react-query'
import type { QueryClientConfig } from '@tanstack/react-query'
import { config } from '@/lib/config'

/**
 * Default query options
 *
 * These options apply to all queries unless overridden.
 */
const defaultQueryOptions = {
  /**
   * Stale time: How long data is considered fresh
   * - Data is considered fresh for this duration
   * - Fresh data won't trigger a refetch
   * - 5 minutes is a good default for most use cases
   */
  staleTime: 5 * 60 * 1000, // 5 minutes

  /**
   * Garbage collection time (formerly cacheTime)
   * - How long unused/inactive data stays in cache
   * - Data is garbage collected after this time if not used
   * - 10 minutes allows for quick navigation back to previous views
   */
  gcTime: 10 * 60 * 1000, // 10 minutes

  /**
   * Retry configuration
   * - Number of retries for failed queries
   * - false = no retries
   * - number = exact number of retries
   * - true = infinite retries (not recommended)
   */
  retry: (failureCount, error: any) => {
    // Don't retry on 4xx errors (client errors)
    if (error?.response?.status >= 400 && error?.response?.status < 500) {
      return false
    }
    // Retry up to 3 times for network/server errors
    return failureCount < 3
  },

  /**
   * Retry delay with exponential backoff
   */
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

  /**
   * Refetch on window focus
   * - false = don't refetch when window regains focus
   * - true = refetch when window regains focus
   * - 'always' = always refetch
   */
  refetchOnWindowFocus: false,

  /**
   * Refetch on reconnect
   * - Automatically refetch when network reconnects
   */
  refetchOnReconnect: true,

  /**
   * Refetch on mount
   * - true = refetch when component mounts (if data is stale)
   * - false = use cached data if available
   */
  refetchOnMount: true,

  /**
   * Network mode
   * - 'online' = only fetch when online
   * - 'always' = always fetch (even when offline, will fail)
   * - 'offlineFirst' = use cache when offline
   */
  networkMode: 'online',
}

/**
 * Default mutation options
 *
 * These options apply to all mutations unless overridden.
 */
const defaultMutationOptions = {
  /**
   * Retry configuration for mutations
   * - Mutations typically shouldn't retry automatically
   * - User should explicitly retry failed mutations
   */
  retry: (failureCount, error: any) => {
    // Only retry network errors, not client errors
    if (error?.response?.status >= 400 && error?.response?.status < 500) {
      return false
    }
    // Retry network errors up to 2 times
    return failureCount < 2
  },

  /**
   * Retry delay for mutations
   */
  retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
}

/**
 * QueryClient configuration
 */
const queryClientConfig: QueryClientConfig = {
  defaultOptions: {
    queries: defaultQueryOptions,
    mutations: defaultMutationOptions,
  },
  /**
   * Logger for development
   */
  logger: {
    log: (...args) => {
      if (config.debug && config.env === 'development') {
        console.log('[React Query]', ...args)
      }
    },
    warn: (...args) => {
      if (config.debug && config.env === 'development') {
        console.warn('[React Query]', ...args)
      }
    },
    error: (...args) => {
      console.error('[React Query]', ...args)
    },
  },
}

/**
 * Create QueryClient instance
 *
 * This is a singleton instance that should be used throughout the app.
 */
export const queryClient = new QueryClient(queryClientConfig)

/**
 * Query Key Factories
 *
 * Centralized query key management for type safety and consistency.
 * All query keys should be generated using these factories.
 */

/**
 * Base query keys
 */
export const queryKeys = {
  /**
   * All query keys
   */
  all: ['queries'] as const,

  /**
   * Assets
   */
  assets: {
    all: ['queries', 'assets'] as const,
    lists: () => [...queryKeys.assets.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.assets.lists(), filters] as const,
    details: () => [...queryKeys.assets.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.assets.details(), id] as const,
    search: (query: string) =>
      [...queryKeys.assets.all, 'search', query] as const,
  },

  /**
   * Users
   */
  users: {
    all: ['queries', 'users'] as const,
    lists: () => [...queryKeys.users.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.users.lists(), filters] as const,
    details: () => [...queryKeys.users.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.users.details(), id] as const,
    current: () => [...queryKeys.users.all, 'current'] as const,
    profile: (id: string) => [...queryKeys.users.all, 'profile', id] as const,
  },

  /**
   * Tenants
   */
  tenants: {
    all: ['queries', 'tenants'] as const,
    lists: () => [...queryKeys.tenants.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.tenants.lists(), filters] as const,
    current: () => [...queryKeys.tenants.all, 'current'] as const,
    detail: (id: string) => [...queryKeys.tenants.all, id] as const,
    config: (id: string) => [...queryKeys.tenants.detail(id), 'config'] as const,
  },

  /**
   * Platform Admin
   */
  platformAdmin: {
    all: ['queries', 'platform-admin'] as const,
    overview: () => [...queryKeys.platformAdmin.all, 'overview'] as const,
    metrics: () => [...queryKeys.platformAdmin.all, 'metrics'] as const,
  },

  /**
   * Workspaces
   */
  workspaces: {
    all: ['queries', 'workspaces'] as const,
    lists: () => [...queryKeys.workspaces.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.workspaces.lists(), filters] as const,
    details: () => [...queryKeys.workspaces.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.workspaces.details(), id] as const,
    current: () => [...queryKeys.workspaces.all, 'current'] as const,
    members: (id: string) =>
      [...queryKeys.workspaces.details(), id, 'members'] as const,
  },

  /**
   * Connections/Integrations
   */
  connections: {
    all: ['queries', 'connections'] as const,
    lists: () => [...queryKeys.connections.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.connections.lists(), filters] as const,
    details: () => [...queryKeys.connections.all, 'detail'] as const,
    detail: (id: string) =>
      [...queryKeys.connections.details(), id] as const,
    status: (id: string) =>
      [...queryKeys.connections.details(), id, 'status'] as const,
  },

  /**
   * Data Quality
   */
  dataQuality: {
    all: ['queries', 'data-quality'] as const,
    checks: () => [...queryKeys.dataQuality.all, 'checks'] as const,
    check: (id: string) =>
      [...queryKeys.dataQuality.checks(), id] as const,
    results: (checkId: string) =>
      [...queryKeys.dataQuality.check(checkId), 'results'] as const,
    metrics: () => [...queryKeys.dataQuality.all, 'metrics'] as const,
  },

  /**
   * Compliance
   */
  compliance: {
    all: ['queries', 'compliance'] as const,
    policies: () => [...queryKeys.compliance.all, 'policies'] as const,
    policy: (id: string) =>
      [...queryKeys.compliance.policies(), id] as const,
    violations: () => [...queryKeys.compliance.all, 'violations'] as const,
    violation: (id: string) =>
      [...queryKeys.compliance.violations(), id] as const,
    scans: () => [...queryKeys.compliance.all, 'scans'] as const,
    scansList: (filters?: Record<string, any>) =>
      [...queryKeys.compliance.scans(), 'list', filters] as const,
    scan: (id: string) => [...queryKeys.compliance.scans(), id] as const,
    scanResults: (id: string) =>
      [...queryKeys.compliance.scan(id), 'results'] as const,
    reports: () => [...queryKeys.compliance.all, 'reports'] as const,
    report: (params?: Record<string, any>) =>
      [...queryKeys.compliance.reports(), params] as const,
  },

  /**
   * Marketplace
   */
  marketplace: {
    all: ['queries', 'marketplace'] as const,
    listings: () => [...queryKeys.marketplace.all, 'listings'] as const,
    listing: (id: string) =>
      [...queryKeys.marketplace.listings(), id] as const,
    categories: () => [...queryKeys.marketplace.all, 'categories'] as const,
    search: (query: string) =>
      [...queryKeys.marketplace.all, 'search', query] as const,
    contracts: {
      all: ['queries', 'marketplace', 'contracts'] as const,
      search: (filters?: Record<string, any>) =>
        ['queries', 'marketplace', 'contracts', 'search', filters] as const,
    },
  },

  /**
   * Search
   */
  search: {
    all: ['queries', 'search'] as const,
    global: (query: string, filters?: Record<string, any>) =>
      [...queryKeys.search.all, 'global', query, filters] as const,
    assets: (query: string, filters?: Record<string, any>) =>
      [...queryKeys.search.all, 'assets', query, filters] as const,
    suggestions: (query: string) =>
      [...queryKeys.search.all, 'suggestions', query] as const,
  },

  /**
   * Analytics
   */
  analytics: {
    all: ['queries', 'analytics'] as const,
    dashboard: () => [...queryKeys.analytics.all, 'dashboard'] as const,
    metrics: (timeRange: string) =>
      [...queryKeys.analytics.all, 'metrics', timeRange] as const,
    reports: () => [...queryKeys.analytics.all, 'reports'] as const,
    report: (id: string) =>
      [...queryKeys.analytics.reports(), id] as const,
  },

  /**
   * Notifications
   */
  notifications: {
    all: ['queries', 'notifications'] as const,
    lists: () => [...queryKeys.notifications.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.notifications.lists(), filters] as const,
    unread: () => [...queryKeys.notifications.all, 'unread'] as const,
    count: () => [...queryKeys.notifications.all, 'count'] as const,
  },

  /**
   * Datasets
   */
  datasets: {
    all: ['queries', 'datasets'] as const,
    lists: () => [...queryKeys.datasets.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.datasets.lists(), filters] as const,
    details: () => [...queryKeys.datasets.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.datasets.details(), id] as const,
    search: (query: string) =>
      [...queryKeys.datasets.all, 'search', query] as const,
  },

  /**
   * Marketplace - contracts
   */
  marketplaceContracts: {
    all: ['queries', 'marketplace', 'contracts'] as const,
    contracts: {
      all: ['queries', 'marketplace', 'contracts'] as const,
      search: (filters?: Record<string, any>) =>
        ['queries', 'marketplace', 'contracts', 'search', filters] as const,
    },
  },

  /**
   * Authentication
   */
  auth: {
    all: ['queries', 'auth'] as const,
    current: () => [...queryKeys.auth.all, 'current'] as const,
    user: () => [...queryKeys.auth.all, 'user'] as const,
  },

  /**
   * Jobs
   */
  jobs: {
    all: ['queries', 'jobs'] as const,
    lists: () => [...queryKeys.jobs.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.jobs.lists(), filters] as const,
    details: () => [...queryKeys.jobs.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.jobs.details(), id] as const,
    statuses: () => [...queryKeys.jobs.all, 'status'] as const,
    status: (id: string) => [...queryKeys.jobs.statuses(), id] as const,
  },

  /**
   * Contracts
   */
  contracts: {
    all: ['queries', 'contracts'] as const,
    lists: () => [...queryKeys.contracts.all, 'list'] as const,
    list: (filters?: Record<string, any>) =>
      [...queryKeys.contracts.lists(), filters] as const,
    details: () => [...queryKeys.contracts.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.contracts.details(), id] as const,
    validate: (id: string) =>
      [...queryKeys.contracts.detail(id), 'validate'] as const,
    publish: (id: string) =>
      [...queryKeys.contracts.detail(id), 'publish'] as const,
  },
} as const

/**
 * Type-safe query key helper
 *
 * Ensures query keys are properly typed and consistent.
 */
export type QueryKey = typeof queryKeys

/**
 * Helper function to invalidate related queries
 *
 * @example
 * ```tsx
 * // Invalidate all asset queries
 * queryClient.invalidateQueries({ queryKey: queryKeys.assets.all })
 *
 * // Invalidate specific asset list
 * queryClient.invalidateQueries({ queryKey: queryKeys.assets.lists() })
 * ```
 */
export function invalidateQueries(
  queryKey: readonly unknown[],
  exact: boolean = false
) {
  return queryClient.invalidateQueries({
    queryKey,
    exact,
  })
}

/**
 * Helper function to reset queries
 *
 * @example
 * ```tsx
 * // Reset all asset queries
 * queryClient.resetQueries({ queryKey: queryKeys.assets.all })
 * ```
 */
export function resetQueries(queryKey: readonly unknown[], exact: boolean = false) {
  return queryClient.resetQueries({
    queryKey,
    exact,
  })
}

/**
 * Helper function to remove queries
 *
 * @example
 * ```tsx
 * // Remove specific asset query
 * queryClient.removeQueries({ queryKey: queryKeys.assets.detail('123') })
 * ```
 */
export function removeQueries(queryKey: readonly unknown[], exact: boolean = false) {
  return queryClient.removeQueries({
    queryKey,
    exact,
  })
}

/**
 * Helper function to prefetch query
 *
 * @example
 * ```tsx
 * // Prefetch asset detail
 * await prefetchQuery({
 *   queryKey: queryKeys.assets.detail('123'),
 *   queryFn: () => api.getAsset('123'),
 * })
 * ```
 */
export async function prefetchQuery<TData = unknown>(
  options: {
    queryKey: readonly unknown[]
    queryFn: () => Promise<TData>
    staleTime?: number
  }
) {
  return queryClient.prefetchQuery({
    queryKey: options.queryKey,
    queryFn: options.queryFn,
    staleTime: options.staleTime,
  })
}

/**
 * Query client is already exported above as a const export
 * No need to re-export it here
 */

