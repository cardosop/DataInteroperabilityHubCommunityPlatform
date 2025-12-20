/**
 * useComplianceScan Hook
 *
 * Query hook for getting a single compliance scan by ID.
 * Provides compliance scan detail functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function ComplianceScanDetail({ scanId }: { scanId: string }) {
 *   const { data, isLoading, error } = useComplianceScan(scanId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <h2>Scan {data?.id}</h2>
 *       <p>Status: {data?.status}</p>
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { getComplianceScan, type ComplianceScan } from '@/lib/api/compliance'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useComplianceScan Hook
 *
 * Query hook for getting a single compliance scan.
 *
 * @param scanId - Compliance scan UUID
 * @param options - Additional React Query options
 * @returns Compliance scan query result
 */
export function useComplianceScan(
  scanId: string | null | undefined,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<ComplianceScan, Error>({
    queryKey: queryKeys.compliance.scan(scanId!),
    queryFn: async () => {
      return await getComplianceScan(scanId!)
    },
    enabled: (options?.enabled !== false) && !!scanId,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

