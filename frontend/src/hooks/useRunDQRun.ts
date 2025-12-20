/**
 * useRunDQRun Hook
 *
 * Mutation hook for creating/running a DQ run.
 * Provides DQ run creation functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function RunDQCheck() {
 *   const runDQRun = useRunDQRun({
 *     onSuccess: (data) => {
 *       showToast('DQ run started successfully')
 *       navigate(`/data-quality/runs/${data.id}`)
 *     },
 *     onError: (error) => {
 *       showToast('Failed to start DQ run: ' + error.message, 'error')
 *     }
 *   })
 *
 *   const handleRun = () => {
 *     runDQRun.mutate({
 *       asset_id: 'asset-123',
 *       profile_key: 'intake_basic_gx'
 *     })
 *   }
 *
 *   return (
 *     <button onClick={handleRun} disabled={runDQRun.isPending}>
 *       {runDQRun.isPending ? 'Starting...' : 'Run DQ Check'}
 *     </button>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query'
import { runDQRun, type RunDQRunRequest, type DQRun } from '@/lib/api/data-quality'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useRunDQRun Hook
 *
 * Mutation hook for creating/running a DQ run.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useRunDQRun(
  options?: Omit<UseMutationOptions<DQRun, Error, RunDQRunRequest>, 'mutationFn' | 'onSuccess'>
) {
  const queryClient = useQueryClient()

  return useMutation<DQRun, Error, RunDQRunRequest>({
    mutationFn: (data: RunDQRunRequest) => runDQRun(data),
    onSuccess: (data, variables) => {
      // Invalidate DQ runs list queries to refresh the list
      queryClient.invalidateQueries({ queryKey: queryKeys.dataQuality.all })

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    ...options,
  })
}

