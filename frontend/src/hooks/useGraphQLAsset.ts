/**
 * useGraphQLAsset Hook
 *
 * Example GraphQL query hook for fetching a single asset.
 * Demonstrates how to use useGraphQLQuery with a specific GraphQL query.
 *
 * @example
 * ```tsx
 * function AssetDetail({ assetId }: { assetId: string }) {
 *   const { data, isLoading, error } = useGraphQLAsset(assetId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <Error message={error.message} />
 *   if (!data?.asset) return <NotFound />
 *
 *   const asset = data.asset
 *
 *   return (
 *     <div>
 *       <h1>{asset.name}</h1>
 *       <p>Status: {asset.status}</p>
 *       <p>Contracts: {asset.contracts?.length || 0}</p>
 *     </div>
 *   )
 * }
 * ```
 */

import { gql } from '@apollo/client'
import { useGraphQLQuery } from './useGraphQLQuery'

/**
 * GraphQL query for getting a single asset
 */
export const GET_ASSET_QUERY = gql`
  query GetAsset($id: ID!) {
    asset(id: $id) {
      id
      key
      name
      description
      domain
      status
      visibility
      dqStatus
      complianceStatus
      contracts {
        id
        name
        status
      }
      datasets {
        id
        name
        format
      }
      createdAt
      updatedAt
    }
  }
`

/**
 * Asset type from GraphQL response
 */
export interface GraphQLAsset {
  id: string
  key: string
  name: string
  description?: string | null
  domain?: string | null
  status: string
  visibility: string
  dqStatus: string
  complianceStatus: string
  contracts?: Array<{
    id: string
    name?: string | null
    status: string
  }> | null
  datasets?: Array<{
    id: string
    name?: string | null
    format?: string | null
  }> | null
  createdAt: string
  updatedAt: string
}

/**
 * GraphQL query response type
 */
export interface GetAssetResponse {
  asset?: GraphQLAsset | null
}

/**
 * useGraphQLAsset Hook
 *
 * Example GraphQL query hook for fetching a single asset by ID.
 *
 * @param id - Asset ID
 * @param options - Additional React Query options
 * @returns Asset query result
 */
export function useGraphQLAsset(
  id: string,
  options?: {
    enabled?: boolean
    staleTime?: number
  }
) {
  return useGraphQLQuery<GetAssetResponse, { id: string }>({
    query: GET_ASSET_QUERY,
    variables: { id },
    queryOptions: {
      enabled: (options?.enabled !== false) && !!id,
      staleTime: options?.staleTime ?? 5 * 60 * 1000, // 5 minutes default
    },
  })
}

