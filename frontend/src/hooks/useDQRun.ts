/**
 * useDQRun Hook
 *
 * Query hook for getting a single DQ run by ID.
 * Provides DQ run detail functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function DQRunDetail({ runId }: { runId: string }) {
 *   const { data, isLoading, error } = useDQRun(runId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <h2>DQ Run {data?.id}</h2>
 *       <p>Status: {data?.status}</p>
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { getDQRun, type DQRun } from '@/lib/api/data-quality'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useDQRun Hook
 *
 * Query hook for getting a single DQ run.
 *
 * @param runId - DQ run UUID
 * @param options - Additional React Query options
 * @returns DQ run query result
 */
export function useDQRun(
  runId: string | null | undefined,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<DQRun, Error>({
    queryKey: queryKeys.dataQuality.check(runId!),
    queryFn: async () => {
      return await getDQRun(runId!)
    },
    enabled: (options?.enabled !== false) && !!runId,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

