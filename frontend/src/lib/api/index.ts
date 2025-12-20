/**
 * API Client
 *
 * API client, WebSocket, and GraphQL setup.
 * Export API clients and utilities from this file.
 */

// Main API client
export { apiClient, default } from './client'
export { createApiClient, getApiClient, createPublicApiClient, createAuthenticatedApiClient } from './client'

// Fetch client factory
export { createFetchClient, FetchError, FetchResponse } from './fetch'
export type { ApiClientOptions, ExtendedFetchRequestInit } from './fetch'

// React Query setup
export { queryClient, queryKeys, invalidateQueries, resetQueries, removeQueries, prefetchQuery } from './react-query'
export { ReactQueryProvider } from './react-query-provider'
export type { QueryKey } from './react-query'

// Types
export * from './types'

// Utilities
export * from './utils'

// Response types
export * from './responses'

// Error handling
export * from './errors'
export * from './exceptions'

// Authentication API
export * from './auth'

// Dataset API
export * from './datasets'

// Assets API
export * from './assets'

// Jobs API
export * from './jobs'

// GraphQL API
export * from './graphql'

// WebSocket API
export * from './websocket'
export * from './websocket-events'

// Audit API
export * from './audit'

// Datasets API
export * from './datasets'

// Marketplace API
export * from './marketplace'

// WebSocket API
export * from './websocket'
