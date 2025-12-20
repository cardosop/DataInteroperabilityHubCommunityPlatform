/**
 * useComplianceScanResults Hook
 *
 * Query hook for getting compliance scan results by scan ID.
 * Provides compliance scan results with detailed violation information.
 *
 * @example
 * ```tsx
 * function ComplianceScanResults({ scanId }: { scanId: string }) {
 *   const { data, isLoading, error } = useComplianceScanResults(scanId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <h2>Compliance Score: {data?.compliance_score}</h2>
 *       <ViolationsList violations={data?.violations} />
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import {
  getComplianceScanResults,
  type ComplianceScanResults,
} from '@/lib/api/compliance'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useComplianceScanResults Hook
 *
 * Query hook for getting compliance scan results.
 *
 * @param scanId - Compliance scan UUID
 * @param options - Additional React Query options
 * @returns Compliance scan results query result
 */
export function useComplianceScanResults(
  scanId: string | null | undefined,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<ComplianceScanResults, Error>({
    queryKey: queryKeys.compliance.scanResults(scanId!),
    queryFn: async () => {
      return await getComplianceScanResults(scanId!)
    },
    enabled: (options?.enabled !== false) && !!scanId,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

