/**
 * useComplianceScans Hook
 *
 * Query hook for listing compliance scans with filtering, sorting, and pagination.
 * Provides compliance scan list functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function ComplianceScansList() {
 *   const { data, isLoading, error } = useComplianceScans({
 *     page: 1,
 *     page_size: 20,
 *     ordering: '-created_at',
 *     status: 'SUCCEEDED'
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(scan => (
 *         <ComplianceScanCard key={scan.id} scan={scan} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import {
  listComplianceScans,
  type ListComplianceScansParams,
  type ListComplianceScansResponse,
} from '@/lib/api/compliance'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useComplianceScans Hook
 *
 * Query hook for listing compliance scans.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Compliance scans list query result
 */
export function useComplianceScans(
  params?: ListComplianceScansParams,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<ListComplianceScansResponse, Error>({
    queryKey: queryKeys.compliance.scansList(params),
    queryFn: async () => {
      return await listComplianceScans(params)
    },
    enabled: options?.enabled !== false,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

