/**
 * usePublishContract Hook
 *
 * Mutation hook for publishing a contract.
 * Provides contract publishing functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function PublishContractButton({ contractId }: { contractId: string }) {
 *   const publishContract = usePublishContract()
 *
 *   const handlePublish = async () => {
 *     try {
 *       const result = await publishContract.mutateAsync({
 *         id: contractId,
 *         data: {}
 *       })
 *       // Show success message
 *       // Redirect to contract detail page
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <button
 *       onClick={handlePublish}
 *       disabled={publishContract.isPending}
 *     >
 *       {publishContract.isPending ? 'Publishing...' : 'Publish Contract'}
 *     </button>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  publishContract,
  type PublishContractRequest,
  type PublishContractResponse,
} from '@/lib/api/contracts'
import { queryKeys } from '@/lib/api/react-query'

/**
 * Publish contract mutation input
 */
export interface PublishContractInput {
  /**
   * Contract ID
   */
  id: string
  /**
   * Publish options
   */
  data?: PublishContractRequest
}

/**
 * usePublishContract Hook
 *
 * Mutation hook for publishing a contract.
 *
 * Note: This endpoint may not exist in all API versions.
 * If the endpoint doesn't exist, the mutation will fail with an error.
 *
 * @returns Publish contract mutation object with mutate, mutateAsync, and state
 */
export function usePublishContract() {
  const queryClient = useQueryClient()

  return useMutation<PublishContractResponse, Error, PublishContractInput>({
    mutationFn: async ({ id, data }) => {
      return await publishContract(id, data)
    },
    onSuccess: (data, variables) => {
      // Invalidate contract lists to refetch
      queryClient.invalidateQueries({
        queryKey: queryKeys.contracts.lists(),
      })

      // Invalidate contract detail to refetch with updated status
      queryClient.invalidateQueries({
        queryKey: queryKeys.contracts.detail(variables.id),
      })

      // Cache publish result
      queryClient.setQueryData(
        queryKeys.contracts.publish(variables.id),
        data
      )
    },
    onError: (error) => {
      // Error handling is done by the caller
      console.error('[PublishContract] Contract publishing failed:', error)
    },
  })
}

