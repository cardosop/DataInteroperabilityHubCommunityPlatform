/**
 * useTenant Hook
 *
 * Query hook for getting current tenant or tenant by ID.
 * Provides tenant detail functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function TenantInfo() {
 *   const { data, isLoading, error } = useTenant()
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <h2>{data?.name}</h2>
 *       <p>Status: {data?.status}</p>
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { getTenant, type Tenant } from '@/lib/api/tenants'
import { queryKeys } from '@/lib/api/react-query'
import { useAuth } from './useAuth'

/**
 * useTenant Hook
 *
 * Query hook for getting current tenant or tenant by ID.
 *
 * @param tenantId - Optional tenant UUID (if not provided, gets current user's tenant)
 * @param options - Additional React Query options
 * @returns Tenant query result
 */
export function useTenant(
  tenantId?: string | null,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  const { user } = useAuth()
  const effectiveTenantId = tenantId || user?.tenant_id

  return useQuery<Tenant, Error>({
    queryKey: effectiveTenantId ? queryKeys.tenants.detail(effectiveTenantId) : queryKeys.tenants.current(),
    queryFn: async () => {
      if (!effectiveTenantId) {
        throw new Error('No tenant ID available')
      }
      return await getTenant(effectiveTenantId)
    },
    enabled: (options?.enabled !== false) && !!effectiveTenantId,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

