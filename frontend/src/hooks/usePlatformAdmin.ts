/**
 * Platform Admin Hooks
 *
 * React Query hooks for platform administration operations:
 * - useTenants() - List all tenants (platform admin only)
 * - useSystemMetrics() - Get system metrics
 * - usePlatformOverview() - Get platform overview statistics
 * - useSuspendTenant() - Suspend tenant mutation
 * - useReactivateTenant() - Reactivate tenant mutation
 */

import { useQuery, useMutation, useQueryClient, UseQueryOptions, UseMutationOptions } from '@tanstack/react-query'
import {
  listTenants,
  suspendTenant,
  reactivateTenant,
  type ListTenantsParams,
  type ListTenantsResponse,
  type Tenant,
  type SuspendTenantRequest,
  type ReactivateTenantRequest,
} from '@/lib/api/tenants'
import { getSystemMetrics, getPlatformOverview, type PlatformOverview } from '@/lib/api/platform-admin'
import { queryKeys, invalidateQueries } from '@/lib/api/react-query'

/**
 * useTenants Hook
 *
 * Query hook for listing all tenants (platform admin only).
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Query result with tenants list
 */
export function useTenants(
  params?: ListTenantsParams,
  options?: Omit<UseQueryOptions<ListTenantsResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<ListTenantsResponse, Error>({
    queryKey: queryKeys.tenants.list(params),
    queryFn: () => listTenants(params),
    ...options,
  })
}

/**
 * useSystemMetrics Hook
 *
 * Query hook for getting system metrics in Prometheus format.
 *
 * @param options - Additional React Query options
 * @returns Query result with system metrics
 */
export function useSystemMetrics(
  options?: Omit<UseQueryOptions<string, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<string, Error>({
    queryKey: queryKeys.platformAdmin.metrics(),
    queryFn: () => getSystemMetrics(),
    staleTime: 30 * 1000, // 30 seconds - metrics should be fresh
    ...options,
  })
}

/**
 * usePlatformOverview Hook
 *
 * Query hook for getting platform overview statistics.
 *
 * @param options - Additional React Query options
 * @returns Query result with platform overview
 */
export function usePlatformOverview(
  options?: Omit<UseQueryOptions<PlatformOverview, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<PlatformOverview, Error>({
    queryKey: queryKeys.platformAdmin.overview(),
    queryFn: () => getPlatformOverview(),
    staleTime: 60 * 1000, // 1 minute - overview can be slightly stale
    ...options,
  })
}

/**
 * useSuspendTenant Hook
 *
 * Mutation hook for suspending a tenant.
 * Automatically invalidates tenant list queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useSuspendTenant(
  options?: Omit<UseMutationOptions<Tenant, Error, { tenantId: string; data?: SuspendTenantRequest }>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  return useMutation<Tenant, Error, { tenantId: string; data?: SuspendTenantRequest }>({
    mutationFn: ({ tenantId, data }) => suspendTenant(tenantId, data),
    onSuccess: (data, variables) => {
      // Invalidate all tenant list queries
      invalidateQueries(queryKeys.tenants.lists())
      // Update the specific tenant in cache
      queryClient.setQueryData(queryKeys.tenants.detail(data.id), data)
      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      options?.onError?.(error, variables, context)
    },
    ...options,
  })
}

/**
 * useReactivateTenant Hook
 *
 * Mutation hook for reactivating a suspended tenant.
 * Automatically invalidates tenant list queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useReactivateTenant(
  options?: Omit<UseMutationOptions<Tenant, Error, { tenantId: string; data?: ReactivateTenantRequest }>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  return useMutation<Tenant, Error, { tenantId: string; data?: ReactivateTenantRequest }>({
    mutationFn: ({ tenantId, data }) => reactivateTenant(tenantId, data),
    onSuccess: (data, variables) => {
      // Invalidate all tenant list queries
      invalidateQueries(queryKeys.tenants.lists())
      // Update the specific tenant in cache
      queryClient.setQueryData(queryKeys.tenants.detail(data.id), data)
      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      options?.onError?.(error, variables, context)
    },
    ...options,
  })
}

