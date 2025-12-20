/**
 * useRunComplianceScan Hook
 *
 * Mutation hook for running/creating a compliance scan.
 * Provides compliance scan creation functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function RunComplianceScanButton({ assetId }: { assetId: string }) {
 *   const runScan = useRunComplianceScan()
 *
 *   const handleRunScan = async () => {
 *     try {
 *       const scan = await runScan.mutateAsync({
 *         asset_id: assetId,
 *         scan_mode: 'internal',
 *         applicable_regulations: ['GDPR', 'CCPA']
 *       })
 *       // Show success message
 *       // Navigate to scan detail page
 *       navigate(`/compliance/scans/${scan.id}`)
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <button
 *       onClick={handleRunScan}
 *       disabled={runScan.isPending}
 *     >
 *       {runScan.isPending ? 'Running Scan...' : 'Run Compliance Scan'}
 *     </button>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  runComplianceScan,
  type RunComplianceScanRequest,
  type ComplianceScan,
} from '@/lib/api/compliance'
import { queryKeys } from '@/lib/api/react-query'

/**
 * useRunComplianceScan Hook
 *
 * Mutation hook for running/creating a compliance scan.
 *
 * @returns Run compliance scan mutation object with mutate, mutateAsync, and state
 */
export function useRunComplianceScan() {
  const queryClient = useQueryClient()

  return useMutation<ComplianceScan, Error, RunComplianceScanRequest>({
    mutationFn: async (data) => {
      return await runComplianceScan(data)
    },
    onSuccess: (data) => {
      // Invalidate compliance scans list to refetch
      queryClient.invalidateQueries({
        queryKey: queryKeys.compliance.scans(),
      })

      // Add the new scan to the cache
      queryClient.setQueryData(
        queryKeys.compliance.scan(data.id),
        data
      )
    },
    onError: (error) => {
      // Error handling is done by the caller
      console.error('[RunComplianceScan] Compliance scan creation failed:', error)
    },
  })
}

