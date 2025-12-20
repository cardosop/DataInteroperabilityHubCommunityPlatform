/**
 * GraphQL Client and Utilities
 *
 * Comprehensive GraphQL client setup with:
 * - Apollo Client integration
 * - Query and mutation examples
 * - Type-safe GraphQL operations
 * - Error handling utilities
 * - Helper functions for common operations
 *
 * This module provides a clean interface for GraphQL operations
 * while leveraging the configured Apollo Client.
 */

import { ApolloClient, DocumentNode, OperationVariables, TypedDocumentNode } from '@apollo/client'
import { apolloClient } from '../config/apollo'
import { gql } from '@apollo/client'
import { config } from '../config'

/**
 * GraphQL client instance
 * Uses the configured Apollo Client
 */
export const graphqlClient: ApolloClient<any> = apolloClient

/**
 * GraphQL error structure
 */
export interface GraphQLError {
  message: string
  locations?: Array<{ line: number; column: number }>
  path?: Array<string | number>
  extensions?: {
    code?: string
    httpStatus?: number
    [key: string]: any
  }
}

/**
 * GraphQL response structure
 */
export interface GraphQLResponse<T = any> {
  data?: T
  errors?: GraphQLError[]
  extensions?: Record<string, any>
}

/**
 * Execute a GraphQL query
 *
 * @param query - GraphQL query document
 * @param variables - Query variables
 * @param options - Additional Apollo Client options
 * @returns Promise with query result
 *
 * @example
 * ```tsx
 * const GET_ASSETS = gql`
 *   query GetAssets($status: AssetStatusEnum) {
 *     assets(status: $status) {
 *       id
 *       name
 *       status
 *     }
 *   }
 * `
 *
 * const result = await executeQuery(GET_ASSETS, { status: 'ACTIVE' })
 * ```
 */
export async function executeQuery<TData = any, TVariables = OperationVariables>(
  query: DocumentNode | TypedDocumentNode<TData, TVariables>,
  variables?: TVariables,
  options?: {
    fetchPolicy?: 'cache-first' | 'cache-and-network' | 'network-only' | 'cache-only' | 'no-cache'
    errorPolicy?: 'none' | 'ignore' | 'all'
  }
): Promise<GraphQLResponse<TData>> {
  try {
    const result = await graphqlClient.query<TData, TVariables>({
      query,
      variables,
      fetchPolicy: options?.fetchPolicy || 'cache-first',
      errorPolicy: options?.errorPolicy || 'all',
    })

    return {
      data: result.data,
      errors: result.errors as GraphQLError[] | undefined,
      extensions: result.extensions,
    }
  } catch (error: any) {
    // Handle network errors
    if (error.networkError) {
      throw new Error(`GraphQL network error: ${error.networkError.message}`)
    }

    // Handle GraphQL errors
    if (error.graphQLErrors && error.graphQLErrors.length > 0) {
      return {
        errors: error.graphQLErrors as GraphQLError[],
        extensions: error.extensions,
      }
    }

    throw error
  }
}

/**
 * Execute a GraphQL mutation
 *
 * @param mutation - GraphQL mutation document
 * @param variables - Mutation variables
 * @param options - Additional Apollo Client options
 * @returns Promise with mutation result
 *
 * @example
 * ```tsx
 * const CREATE_ASSET = gql`
 *   mutation CreateAsset($input: AssetInput!) {
 *     createAsset(input: $input) {
 *       id
 *       name
 *       status
 *     }
 *   }
 * `
 *
 * const result = await executeMutation(CREATE_ASSET, {
 *   input: { name: 'New Asset', key: 'new-asset' }
 * })
 * ```
 */
export async function executeMutation<TData = any, TVariables = OperationVariables>(
  mutation: DocumentNode | TypedDocumentNode<TData, TVariables>,
  variables?: TVariables,
  options?: {
    errorPolicy?: 'none' | 'ignore' | 'all'
    refetchQueries?: Array<{ query: DocumentNode; variables?: any }>
  }
): Promise<GraphQLResponse<TData>> {
  try {
    const result = await graphqlClient.mutate<TData, TVariables>({
      mutation,
      variables,
      errorPolicy: options?.errorPolicy || 'all',
      refetchQueries: options?.refetchQueries,
    })

    return {
      data: result.data,
      errors: result.errors as GraphQLError[] | undefined,
      extensions: result.extensions,
    }
  } catch (error: any) {
    // Handle network errors
    if (error.networkError) {
      throw new Error(`GraphQL network error: ${error.networkError.message}`)
    }

    // Handle GraphQL errors
    if (error.graphQLErrors && error.graphQLErrors.length > 0) {
      return {
        errors: error.graphQLErrors as GraphQLError[],
        extensions: error.extensions,
      }
    }

    throw error
  }
}

/**
 * Execute a GraphQL subscription (for real-time updates)
 *
 * Note: This requires WebSocket support. Currently, the backend
 * GraphQL implementation may not support subscriptions.
 *
 * @param subscription - GraphQL subscription document
 * @param variables - Subscription variables
 * @param onNext - Callback for subscription updates
 * @param onError - Callback for subscription errors
 * @returns Subscription object with unsubscribe method
 */
export function executeSubscription<TData = any, TVariables = OperationVariables>(
  subscription: DocumentNode | TypedDocumentNode<TData, TVariables>,
  variables?: TVariables,
  onNext?: (data: TData) => void,
  onError?: (error: Error) => void
) {
  return graphqlClient.subscribe<TData, TVariables>({
    query: subscription,
    variables,
  }).subscribe({
    next: (result) => {
      if (result.data && onNext) {
        onNext(result.data)
      }
      if (result.errors && onError) {
        onError(new Error(result.errors.map(e => e.message).join(', ')))
      }
    },
    error: (error) => {
      if (onError) {
        onError(error)
      } else if (config.development.enableApiLogging) {
        console.error('[GraphQL Subscription Error]:', error)
      }
    },
  })
}

/**
 * Check if GraphQL response has errors
 *
 * @param response - GraphQL response
 * @returns True if response has errors
 */
export function hasGraphQLErrors(response: GraphQLResponse): boolean {
  return !!(response.errors && response.errors.length > 0)
}

/**
 * Get first error message from GraphQL response
 *
 * @param response - GraphQL response
 * @returns First error message or null
 */
export function getFirstErrorMessage(response: GraphQLResponse): string | null {
  if (!response.errors || response.errors.length === 0) {
    return null
  }
  return response.errors[0].message
}

/**
 * Get all error messages from GraphQL response
 *
 * @param response - GraphQL response
 * @returns Array of error messages
 */
export function getAllErrorMessages(response: GraphQLResponse): string[] {
  if (!response.errors || response.errors.length === 0) {
    return []
  }
  return response.errors.map((error) => error.message)
}

// ============================================================================
// Example Queries
// ============================================================================

/**
 * Example: Get assets query
 *
 * @example
 * ```tsx
 * const GET_ASSETS = gql`
 *   query GetAssets($status: AssetStatusEnum, $first: Int, $after: String) {
 *     assets(status: $status, first: $first, after: $after) {
 *       edges {
 *         node {
 *           id
 *           key
 *           name
 *           description
 *           status
 *           visibility
 *           createdAt
 *         }
 *       }
 *       pageInfo {
 *         hasNextPage
 *         hasPreviousPage
 *         startCursor
 *         endCursor
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeQuery(GET_ASSETS, {
 *   status: 'ACTIVE',
 *   first: 20
 * })
 * ```
 */
export const GET_ASSETS_QUERY = gql`
  query GetAssets($status: AssetStatusEnum, $first: Int, $after: String) {
    assets(status: $status, first: $first, after: $after) {
      edges {
        node {
          id
          key
          name
          description
          domain
          status
          visibility
          dqStatus
          complianceStatus
          createdAt
          updatedAt
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
`

/**
 * Example: Get single asset query
 *
 * @example
 * ```tsx
 * const GET_ASSET = gql`
 *   query GetAsset($id: ID!) {
 *     asset(id: $id) {
 *       id
 *       key
 *       name
 *       description
 *       status
 *       contracts {
 *         id
 *         name
 *         status
 *       }
 *       datasets {
 *         id
 *         name
 *         format
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeQuery(GET_ASSET, { id: 'asset-123' })
 * ```
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
 * Example: Get contracts query
 *
 * @example
 * ```tsx
 * const GET_CONTRACTS = gql`
 *   query GetContracts($status: ContractStatusEnum, $first: Int) {
 *     contracts(status: $status, first: $first) {
 *       edges {
 *         node {
 *           id
 *           name
 *           status
 *           originalSpecType
 *           createdAt
 *         }
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeQuery(GET_CONTRACTS, { status: 'ACTIVE' })
 * ```
 */
export const GET_CONTRACTS_QUERY = gql`
  query GetContracts($status: ContractStatusEnum, $first: Int, $after: String) {
    contracts(status: $status, first: $first, after: $after) {
      edges {
        node {
          id
          name
          status
          originalSpecType
          originalSpecVersion
          hubContractVersion
          validationStatus
          createdAt
          updatedAt
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
`

/**
 * Example: Get current user query
 *
 * @example
 * ```tsx
 * const GET_CURRENT_USER = gql`
 *   query GetCurrentUser {
 *     me {
 *       id
 *       email
 *       displayName
 *       roles
 *       tenant {
 *         id
 *         name
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeQuery(GET_CURRENT_USER)
 * ```
 */
export const GET_CURRENT_USER_QUERY = gql`
  query GetCurrentUser {
    me {
      id
      email
      displayName
      roles
      tenant {
        id
        name
        slug
      }
      createdAt
    }
  }
`

/**
 * Example: Get jobs query
 *
 * @example
 * ```tsx
 * const GET_JOBS = gql`
 *   query GetJobs($status: JobStatusEnum, $type: JobTypeEnum, $first: Int) {
 *     jobs(status: $status, type: $type, first: $first) {
 *       edges {
 *         node {
 *           id
 *           type
 *           status
 *           resourceType
 *           resourceId
 *           startedAt
 *           completedAt
 *           errorMessage
 *         }
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeQuery(GET_JOBS, { status: 'RUNNING' })
 * ```
 */
export const GET_JOBS_QUERY = gql`
  query GetJobs($status: JobStatusEnum, $type: JobTypeEnum, $first: Int, $after: String) {
    jobs(status: $status, type: $type, first: $first, after: $after) {
      edges {
        node {
          id
          type
          status
          resourceType
          resourceId
          startedAt
          completedAt
          errorMessage
          resultJson
          createdAt
          updatedAt
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
`

// ============================================================================
// Example Mutations
// ============================================================================

/**
 * Example: Create asset mutation
 *
 * Note: This is an example. Actual mutations depend on the GraphQL schema.
 * Check the backend GraphQL schema for available mutations.
 *
 * @example
 * ```tsx
 * const CREATE_ASSET = gql`
 *   mutation CreateAsset($input: AssetInput!) {
 *     createAsset(input: $input) {
 *       asset {
 *         id
 *         key
 *         name
 *         status
 *       }
 *       errors {
 *         field
 *         message
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeMutation(CREATE_ASSET, {
 *   input: {
 *     key: 'new-asset',
 *     name: 'New Asset',
 *     description: 'Asset description',
 *     domain: 'finance',
 *     visibility: 'INTERNAL'
 *   }
 * })
 * ```
 */
export const CREATE_ASSET_MUTATION = gql`
  mutation CreateAsset($input: AssetInput!) {
    createAsset(input: $input) {
      asset {
        id
        key
        name
        description
        domain
        status
        visibility
        createdAt
      }
      errors {
        field
        message
      }
    }
  }
`

/**
 * Example: Update asset mutation
 *
 * @example
 * ```tsx
 * const UPDATE_ASSET = gql`
 *   mutation UpdateAsset($id: ID!, $input: AssetUpdateInput!) {
 *     updateAsset(id: $id, input: $input) {
 *       asset {
 *         id
 *         name
 *         description
 *         status
 *       }
 *       errors {
 *         field
 *         message
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeMutation(UPDATE_ASSET, {
 *   id: 'asset-123',
 *   input: {
 *     name: 'Updated Asset Name',
 *     description: 'Updated description'
 *   }
 * })
 * ```
 */
export const UPDATE_ASSET_MUTATION = gql`
  mutation UpdateAsset($id: ID!, $input: AssetUpdateInput!) {
    updateAsset(id: $id, input: $input) {
      asset {
        id
        key
        name
        description
        domain
        status
        visibility
        updatedAt
      }
      errors {
        field
        message
      }
    }
  }
`

/**
 * Example: Validate contract mutation
 *
 * @example
 * ```tsx
 * const VALIDATE_CONTRACT = gql`
 *   mutation ValidateContract($id: ID!) {
 *     validateContract(id: $id) {
 *       contract {
 *         id
 *         validationStatus
 *       }
 *       job {
 *         id
 *         status
 *       }
 *       errors {
 *         field
 *         message
 *       }
 *     }
 *   }
 * `
 *
 * const result = await executeMutation(VALIDATE_CONTRACT, {
 *   id: 'contract-123'
 * })
 * ```
 */
export const VALIDATE_CONTRACT_MUTATION = gql`
  mutation ValidateContract($id: ID!) {
    validateContract(id: $id) {
      contract {
        id
        validationStatus
        updatedAt
      }
      job {
        id
        type
        status
      }
      errors {
        field
        message
      }
    }
  }
`

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Clear Apollo Client cache
 *
 * Useful for logging out or resetting application state
 */
export function clearGraphQLCache(): Promise<void> {
  return graphqlClient.clearStore()
}

/**
 * Reset Apollo Client cache and refetch active queries
 */
export function resetGraphQLCache(): Promise<void> {
  return graphqlClient.resetStore()
}

/**
 * Re-fetch all active queries
 */
export function refetchAllQueries(): Promise<void> {
  return graphqlClient.refetchQueries({ include: 'active' })
}

/**
 * Export gql for convenience
 */
export { gql } from '@apollo/client'

/**
 * Export Apollo Client types for convenience
 */
export type { DocumentNode, OperationVariables, TypedDocumentNode } from '@apollo/client'

