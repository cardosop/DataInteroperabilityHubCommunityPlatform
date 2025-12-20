/**
 * useDQRunResults Hook
 *
 * Query hook for getting DQ run results by run ID.
 * Provides DQ run results with detailed check information.
 *
 * @example
 * ```tsx
 * function DQRunResults({ runId }: { runId: string }) {
 *   const { data, isLoading, error } = useDQRunResults(runId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return (
 *     <div>
 *       <h2>Quality Score: {data?.overall_score}</h2>
 *       <ChecksList checks={data?.checks} />
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { getDQRunResults, type DQRunResults } from '@/lib/api/data-quality'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useDQRunResults Hook
 *
 * Query hook for getting DQ run results.
 *
 * @param runId - DQ run UUID
 * @param options - Additional React Query options
 * @returns DQ run results query result
 */
export function useDQRunResults(
  runId: string | null | undefined,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<DQRunResults, Error>({
    queryKey: queryKeys.dataQuality.results(runId!),
    queryFn: async () => {
      return await getDQRunResults(runId!)
    },
    enabled: (options?.enabled !== false) && !!runId,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

