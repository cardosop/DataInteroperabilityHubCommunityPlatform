/**
 * useUpdateContract Hook
 *
 * Mutation hook for updating an existing contract.
 * Provides contract update functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function UpdateContractForm({ contractId }: { contractId: string }) {
 *   const updateContract = useUpdateContract()
 *
 *   const handleSubmit = async (e: FormEvent) => {
 *     e.preventDefault()
 *     try {
 *       await updateContract.mutateAsync({
 *         id: contractId,
 *         data: {
 *           original_raw: updatedContractJson,
 *           original_format: 'JSON'
 *         }
 *       })
 *       // Show success message
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <!-- form fields -->
 *       <button disabled={updateContract.isPending}>Update Contract</button>
 *     </form>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  updateContract,
  type UpdateContractRequest,
  type Contract,
} from '@/lib/api/contracts'
import { queryKeys } from '@/lib/api/react-query'

/**
 * Update contract mutation input
 */
export interface UpdateContractInput {
  /**
   * Contract ID
   */
  id: string
  /**
   * Update data
   */
  data: UpdateContractRequest
}

/**
 * useUpdateContract Hook
 *
 * Mutation hook for updating an existing contract.
 *
 * @returns Update contract mutation object with mutate, mutateAsync, and state
 */
export function useUpdateContract() {
  const queryClient = useQueryClient()

  return useMutation<Contract, Error, UpdateContractInput>({
    mutationFn: async ({ id, data }) => {
      return await updateContract(id, data)
    },
    onSuccess: (data, variables) => {
      // Invalidate contract lists to refetch
      queryClient.invalidateQueries({
        queryKey: queryKeys.contracts.lists(),
      })

      // Update the contract in the cache
      queryClient.setQueryData(
        queryKeys.contracts.detail(variables.id),
        data
      )

      // Invalidate related queries (validation, etc.)
      queryClient.invalidateQueries({
        queryKey: queryKeys.contracts.detail(variables.id),
      })
    },
    onError: (error) => {
      // Error handling is done by the caller
      console.error('[UpdateContract] Contract update failed:', error)
    },
  })
}

