/**
 * useTenantMutations Hook
 *
 * Mutation hooks for tenant management operations:
 * - Update tenant
 * - Update tenant configuration
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query'
import {
  updateTenant,
  updateTenantConfig,
  type UpdateTenantRequest,
  type UpdateTenantConfigRequest,
  type Tenant,
  type TenantConfig,
} from '@/lib/api/tenants'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useUpdateTenant Hook
 *
 * Mutation hook for updating a tenant.
 */
export function useUpdateTenant(
  options?: Omit<UseMutationOptions<Tenant, Error, { id: string; data: UpdateTenantRequest }>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<Tenant, Error, { id: string; data: UpdateTenantRequest }>({
    mutationFn: ({ id, data }) => updateTenant(id, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.detail(data.id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.current() })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

/**
 * useUpdateTenantConfig Hook
 *
 * Mutation hook for updating tenant configuration.
 */
export function useUpdateTenantConfig(
  options?: Omit<UseMutationOptions<TenantConfig, Error, { tenantId: string; data: UpdateTenantConfigRequest }>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<TenantConfig, Error, { tenantId: string; data: UpdateTenantConfigRequest }>({
    mutationFn: ({ tenantId, data }) => updateTenantConfig(tenantId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.config(data.tenant_id) })
      queryClient.invalidateQueries({ queryKey: queryKeys.tenants.detail(data.tenant_id) })
      options?.onSuccess?.(undefined as any, undefined as any, undefined as any)
    },
    ...options,
  })
}

