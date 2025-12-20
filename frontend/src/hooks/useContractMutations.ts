/**
 * Contract Mutation Hooks
 *
 * React Query hooks for contract mutations:
 * - useCreateContract - Create new contract
 * - useUpdateContract - Update existing contract
 * - useDeleteContract - Delete contract
 * - useValidateContract - Validate contract
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query'
import {
  createContract,
  updateContract,
  deleteContract,
  validateContract,
  type Contract,
  type CreateContractRequest,
  type UpdateContractRequest,
  type ValidateContractRequest,
  type ValidateContractResponse,
} from '@/lib/api/contracts'
import { queryKeys, invalidateQueries } from '@/lib/api/react-query'

/**
 * useCreateContract Hook
 *
 * Mutation hook for creating a new contract.
 * Automatically invalidates contract list queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useCreateContract(
  options?: Omit<UseMutationOptions<Contract, Error, CreateContractRequest>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  return useMutation<Contract, Error, CreateContractRequest>({
    mutationFn: createContract,
    onSuccess: (data) => {
      // Invalidate all contract list queries to refetch with new contract
      invalidateQueries(queryKeys.contracts.lists())

      // Optionally set the new contract in cache for immediate access
      queryClient.setQueryData(queryKeys.contracts.detail(data.id), data)

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, data as any, undefined as any)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      options?.onError?.(error, variables, context)
    },
    ...options,
  })
}

/**
 * useUpdateContract Hook
 *
 * Mutation hook for updating an existing contract.
 * Automatically invalidates related queries and updates cache on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useUpdateContract(
  options?: Omit<
    UseMutationOptions<Contract, Error, { id: string; data: UpdateContractRequest }>,
    'mutationFn'
  >
) {
  const queryClient = useQueryClient()

  return useMutation<Contract, Error, { id: string; data: UpdateContractRequest }>({
    mutationFn: ({ id, data }) => updateContract(id, data),
    onSuccess: (data, variables) => {
      // Invalidate contract list queries
      invalidateQueries(queryKeys.contracts.lists())

      // Update the specific contract in cache
      queryClient.setQueryData(queryKeys.contracts.detail(variables.id), data)

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      options?.onError?.(error, variables, context)
    },
    ...options,
  })
}

/**
 * useDeleteContract Hook
 *
 * Mutation hook for deleting a contract.
 * Automatically invalidates related queries on success.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useDeleteContract(
  options?: Omit<UseMutationOptions<void, Error, string>, 'mutationFn'>
) {
  const queryClient = useQueryClient()

  return useMutation<void, Error, string>({
    mutationFn: deleteContract,
    onSuccess: (data, contractId) => {
      // Invalidate contract list queries
      invalidateQueries(queryKeys.contracts.lists())

      // Remove the contract from cache
      queryClient.removeQueries({ queryKey: queryKeys.contracts.detail(contractId) })

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, contractId, undefined as any)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      options?.onError?.(error, variables, context)
    },
    ...options,
  })
}

/**
 * useValidateContract Hook
 *
 * Mutation hook for validating a contract.
 * Does not invalidate queries as validation is a read operation.
 *
 * @param options - Additional React Query mutation options
 * @returns Mutation object with mutate, mutateAsync, and state
 */
export function useValidateContract(
  options?: Omit<
    UseMutationOptions<ValidateContractResponse, Error, { id: string; data?: ValidateContractRequest }>,
    'mutationFn'
  >
) {
  const queryClient = useQueryClient()

  return useMutation<ValidateContractResponse, Error, { id: string; data?: ValidateContractRequest }>({
    mutationFn: ({ id, data }) => validateContract(id, data),
    onSuccess: (data, variables) => {
      // Optionally update contract in cache with validation status
      // This depends on whether the API returns updated contract data
      // For now, we'll just call the custom onSuccess

      // Call custom onSuccess if provided
      options?.onSuccess?.(data, variables, undefined as any)
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      options?.onError?.(error, variables, context)
    },
    ...options,
  })
}

