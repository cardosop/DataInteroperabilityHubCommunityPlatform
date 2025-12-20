/**
 * useValidateContract Hook
 *
 * Mutation hook for validating a contract.
 * Provides contract validation functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function ValidateContractButton({ contractId }: { contractId: string }) {
 *   const validateContract = useValidateContract()
 *
 *   const handleValidate = async () => {
 *     try {
 *       const result = await validateContract.mutateAsync({
 *         id: contractId,
 *         data: { async: false }
 *       })
 *
 *       if (result.validation_status === 'VALID') {
 *         // Show success message
 *       } else {
 *         // Show errors/warnings
 *       }
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <button
 *       onClick={handleValidate}
 *       disabled={validateContract.isPending}
 *     >
 *       {validateContract.isPending ? 'Validating...' : 'Validate Contract'}
 *     </button>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  validateContract,
  type ValidateContractRequest,
  type ValidateContractResponse,
} from '@/lib/api/contracts'
import { queryKeys } from '@/lib/api/react-query'

/**
 * Validate contract mutation input
 */
export interface ValidateContractInput {
  /**
   * Contract ID
   */
  id: string
  /**
   * Validation options
   */
  data?: ValidateContractRequest
}

/**
 * useValidateContract Hook
 *
 * Mutation hook for validating a contract.
 *
 * @returns Validate contract mutation object with mutate, mutateAsync, and state
 */
export function useValidateContract() {
  const queryClient = useQueryClient()

  return useMutation<ValidateContractResponse, Error, ValidateContractInput>({
    mutationFn: async ({ id, data }) => {
      return await validateContract(id, data)
    },
    onSuccess: (data, variables) => {
      // Invalidate contract detail to refetch with updated validation status
      queryClient.invalidateQueries({
        queryKey: queryKeys.contracts.detail(variables.id),
      })

      // Cache validation result
      queryClient.setQueryData(
        queryKeys.contracts.validate(variables.id),
        data
      )
    },
    onError: (error) => {
      // Error handling is done by the caller
      console.error('[ValidateContract] Contract validation failed:', error)
    },
  })
}

