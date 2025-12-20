/**
 * useDQRuns Hook
 *
 * Query hook for listing DQ runs with filtering, sorting, and pagination.
 * Provides DQ run list functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function DQRunsList() {
 *   const { data, isLoading, error } = useDQRuns({
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
 *       {data?.results.map(run => (
 *         <DQRunCard key={run.id} run={run} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */

import { useQuery } from '@tanstack/react-query'
import { listDQRuns, type ListDQRunsParams, type ListDQRunsResponse } from '@/lib/api/data-quality'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useDQRuns Hook
 *
 * Query hook for listing DQ runs.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns DQ runs list query result
 */
export function useDQRuns(
  params?: ListDQRunsParams,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useQuery<ListDQRunsResponse, Error>({
    queryKey: [...queryKeys.dataQuality.all, 'runs', params],
    queryFn: async () => {
      return await listDQRuns(params)
    },
    enabled: options?.enabled !== false,
    staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
  })
}

