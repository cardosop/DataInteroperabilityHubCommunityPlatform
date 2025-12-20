/**
 * useGraphQLMutation Hook
 *
 * Generic GraphQL mutation hook that integrates Apollo Client with React Query.
 * Provides GraphQL mutation functionality with React Query state management.
 *
 * This hook bridges Apollo Client's GraphQL capabilities with React Query's
 * powerful caching and state management features.
 *
 * @example
 * ```tsx
 * import { gql } from '@apollo/client'
 * import { useGraphQLMutation } from '@/hooks/useGraphQLMutation'
 *
 * const CREATE_ASSET = gql`
 *   mutation CreateAsset($input: AssetInput!) {
 *     createAsset(input: $input) {
 *       asset {
 *         id
 *         name
 *       }
 *       errors {
 *         field
 *         message
 *       }
 *     }
 *   }
 * `
 *
 * function CreateAssetForm() {
 *   const createAsset = useGraphQLMutation({
 *     mutation: CREATE_ASSET
 *   })
 *
 *   const handleSubmit = async (e: FormEvent) => {
 *     e.preventDefault()
 *     try {
 *       const result = await createAsset.mutateAsync({
 *         input: {
 *           name: 'New Asset',
 *           key: 'new-asset'
 *         }
 *       })
 *       // Handle success
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <!-- form fields -->
 *       <button disabled={createAsset.isPending}>Create</button>
 *     </form>
 *   )
 * }
 * ```
 */

import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from '@tanstack/react-query'
import { DocumentNode, OperationVariables, TypedDocumentNode } from '@apollo/client'
import { executeMutation, GraphQLResponse } from '@/lib/api/graphql'

/**
 * GraphQL mutation hook options
 */
export interface UseGraphQLMutationOptions<TData = any, TVariables = OperationVariables> {
  /**
   * GraphQL mutation document
   */
  mutation: DocumentNode | TypedDocumentNode<TData, TVariables>
  /**
   * Apollo Client error policy
   */
  errorPolicy?: 'none' | 'ignore' | 'all'
  /**
   * React Query mutation options
   */
  mutationOptions?: Omit<
    UseMutationOptions<GraphQLResponse<TData>, Error, TVariables>,
    'mutationFn'
  >
}

/**
 * useGraphQLMutation Hook
 *
 * Generic GraphQL mutation hook that integrates Apollo Client with React Query.
 *
 * @param options - GraphQL mutation options
 * @returns GraphQL mutation object with mutate, mutateAsync, and state
 */
export function useGraphQLMutation<TData = any, TVariables = OperationVariables>(
  options: UseGraphQLMutationOptions<TData, TVariables>
) {
  const { mutation, errorPolicy, mutationOptions } = options
  const queryClient = useQueryClient()

  return useMutation<GraphQLResponse<TData>, Error, TVariables>({
    mutationFn: async (variables) => {
      return await executeMutation<TData, TVariables>(mutation, variables, {
        errorPolicy,
      })
    },
    onSuccess: (data, variables, context) => {
      // Invalidate all GraphQL queries to refetch
      queryClient.invalidateQueries({
        queryKey: ['graphql'],
      })

      // Call custom onSuccess if provided
      if (mutationOptions?.onSuccess) {
        mutationOptions.onSuccess(data, variables, context)
      }
    },
    onError: (error, variables, context) => {
      // Call custom onError if provided
      if (mutationOptions?.onError) {
        mutationOptions.onError(error, variables, context)
      } else {
        console.error('[GraphQL Mutation Error]:', error)
      }
    },
    ...mutationOptions,
  })
}

