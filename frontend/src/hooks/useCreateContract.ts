/**
 * useCreateContract Hook
 *
 * Mutation hook for creating a new contract.
 * Provides contract creation functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function CreateContractForm() {
 *   const createContract = useCreateContract()
 *
 *   const handleSubmit = async (e: FormEvent) => {
 *     e.preventDefault()
 *     try {
 *       const contract = await createContract.mutateAsync({
 *         original_raw: contractJson,
 *         original_format: 'JSON',
 *         asset_id: assetId
 *       })
 *       // Redirect to contract detail page
 *       navigate(`/contracts/${contract.id}`)
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <!-- form fields -->
 *       <button disabled={createContract.isPending}>Create Contract</button>
 *     </form>
 *   )
 * }
 * ```
 */

import { createContract, type Contract, type CreateContractRequest } from '@/lib/api/contracts'
import { queryKeys } from '@/lib/api/react-query'
import { useMutation, useQueryClient } from '@tanstack/react-query'

/**
 * useCreateContract Hook
 *
 * Mutation hook for creating a new contract.
 *
 * @returns Create contract mutation object with mutate, mutateAsync, and state
 */
export function useCreateContract() {
  const queryClient = useQueryClient()

  return useMutation<Contract, Error, CreateContractRequest>({
    mutationFn: async data => {
      return await createContract(data)
    },
    onSuccess: data => {
      // Invalidate contract lists to refetch
      queryClient.invalidateQueries({
        queryKey: queryKeys.contracts.lists(),
      })

      // Add the new contract to the cache
      queryClient.setQueryData(queryKeys.contracts.detail(data.id), data)
    },
    onError: error => {
      // Error handling is done by the caller
      console.error('[CreateContract] Contract creation failed:', error)
    },
  })
}
