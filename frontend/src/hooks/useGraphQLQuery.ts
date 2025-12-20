/**
 * useGraphQLQuery Hook
 *
 * Generic GraphQL query hook that integrates Apollo Client with React Query.
 * Provides GraphQL query functionality with React Query caching and state management.
 *
 * This hook bridges Apollo Client's GraphQL capabilities with React Query's
 * powerful caching and state management features.
 *
 * @example
 * ```tsx
 * import { gql } from '@apollo/client'
 * import { useGraphQLQuery } from '@/hooks/useGraphQLQuery'
 *
 * const GET_ASSET = gql`
 *   query GetAsset($id: ID!) {
 *     asset(id: $id) {
 *       id
 *       name
 *       status
 *     }
 *   }
 * `
 *
 * function AssetDetail({ assetId }: { assetId: string }) {
 *   const { data, isLoading, error } = useGraphQLQuery({
 *     query: GET_ASSET,
 *     variables: { id: assetId }
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *
 *   return <div>{data?.asset?.name}</div>
 * }
 * ```
 */

import { useQuery, UseQueryOptions } from '@tanstack/react-query'
import { DocumentNode, OperationVariables, TypedDocumentNode } from '@apollo/client'
import { executeQuery, GraphQLResponse } from '@/lib/api/graphql'

/**
 * GraphQL query hook options
 */
export interface UseGraphQLQueryOptions<TData = any, TVariables = OperationVariables> {
  /**
   * GraphQL query document
   */
  query: DocumentNode | TypedDocumentNode<TData, TVariables>
  /**
   * Query variables
   */
  variables?: TVariables
  /**
   * Apollo Client fetch policy
   */
  fetchPolicy?: 'cache-first' | 'cache-and-network' | 'network-only' | 'cache-only' | 'no-cache'
  /**
   * Apollo Client error policy
   */
  errorPolicy?: 'none' | 'ignore' | 'all'
  /**
   * React Query options
   */
  queryOptions?: Omit<
    UseQueryOptions<GraphQLResponse<TData>, Error>,
    'queryKey' | 'queryFn'
  >
}

/**
 * useGraphQLQuery Hook
 *
 * Generic GraphQL query hook that integrates Apollo Client with React Query.
 *
 * @param options - GraphQL query options
 * @returns GraphQL query result with React Query state management
 */
export function useGraphQLQuery<TData = any, TVariables = OperationVariables>(
  options: UseGraphQLQueryOptions<TData, TVariables>
) {
  const { query, variables, fetchPolicy, errorPolicy, queryOptions } = options

  // Generate query key from query string and variables
  // This ensures proper cache invalidation and deduplication
  const queryKey = [
    'graphql',
    'query',
    query.loc?.source.body || String(query),
    variables,
  ] as const

  return useQuery<GraphQLResponse<TData>, Error>({
    queryKey,
    queryFn: async () => {
      return await executeQuery<TData, TVariables>(query, variables, {
        fetchPolicy,
        errorPolicy,
      })
    },
    staleTime: queryOptions?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
    ...queryOptions,
  })
}

