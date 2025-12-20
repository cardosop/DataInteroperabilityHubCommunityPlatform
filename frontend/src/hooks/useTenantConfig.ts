/**
 * useTenantConfig Hook
 *
 * Query hook for getting tenant configuration.
 * Provides tenant configuration functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function TenantSettings({ tenantId }: { tenantId: string }) {
 *   const { data, isLoading, error } = useTenantConfig(tenantId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <p>DQ Profile: {data?.default_dq_profile}</p>
 *       <p>Retention: {data?.data_retention_days} days</p>
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { getTenantConfig, type TenantConfig } from '@/lib/api/tenants'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useTenantConfig Hook
 *
 * Query hook for getting tenant configuration.
 *
 * @param tenantId - Tenant UUID
 * @param options - Additional React Query options
 * @returns Tenant configuration query result
 */
export function useTenantConfig(
  tenantId: string | null | undefined,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<TenantConfig, Error>({
    queryKey: queryKeys.tenants.config(tenantId!),
    queryFn: async () => {
      return await getTenantConfig(tenantId!)
    },
    enabled: (options?.enabled !== false) && !!tenantId,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

