/**
 * Apollo Client Configuration
 *
 * Centralized configuration for Apollo GraphQL client.
 * Integrates with the authentication service for token management.
 */
import { ApolloClient, InMemoryCache, createHttpLink, from } from '@apollo/client'
import { setContext } from '@apollo/client/link/context'
import { onError } from '@apollo/client/link/error'
import { config } from './env'
// Lazy import to avoid circular dependency - functions are called at runtime

const httpLink = createHttpLink({
  uri: config.api.graphqlUrl,
  credentials: 'include',
})

// Auth link to add JWT token and tenant ID to requests
// Uses direct function calls (not lazy import) since these are simple getters
// The circular dependency is broken by making client.ts use lazy import
const authLink = setContext((_, { headers }) => {
  const token = getAuthToken()
  const tenantId = getTenantId()

  return {
    headers: {
      ...headers,
      authorization: token ? `Bearer ${token}` : '',
      ...(tenantId && { 'X-Tenant-ID': tenantId }),
    },
  }
})

// Error link for handling GraphQL errors
const errorLink = onError(({ graphQLErrors, networkError, operation, forward }) => {
  if (graphQLErrors) {
    graphQLErrors.forEach(({ message, locations, path, extensions }) => {
      const errorDetails = {
        message,
        locations,
        path,
        code: extensions?.code,
        httpStatus: extensions?.httpStatus,
      }

      if (config.development.enableApiLogging) {
        console.error('[GraphQL error]:', errorDetails)
      }

      // Handle authentication errors
      if (extensions?.code === 'UNAUTHENTICATED' || extensions?.httpStatus === 401) {
        // Token might be expired, but we don't handle refresh here
        // The auth service handles token refresh automatically
        if (config.development.enableApiLogging) {
          console.warn('[GraphQL] Authentication error - token may need refresh')
        }
      }
    })
  }

  if (networkError) {
    if (config.development.enableApiLogging) {
      console.error('[GraphQL network error]:', networkError)
    }

    // Handle network errors
    if ('statusCode' in networkError) {
      const statusCode = (networkError as any).statusCode
      if (statusCode === 401) {
        // Unauthorized - token might be invalid
        if (config.development.enableApiLogging) {
          console.warn('[GraphQL] Unauthorized - token may be invalid')
        }
      }
    }
  }
})

/**
 * Apollo Client instance
 *
 * Configured with:
 * - Authentication headers (JWT token + tenant ID)
 * - Error handling
 * - In-memory cache with type policies
 * - Default query options
 */
export const apolloClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          // Add field policies for caching strategies
          // Example: merge functions for paginated queries
        },
      },
      // Add type-specific policies as needed
      // Asset: {
      //   fields: {
      //     contracts: {
      //       merge(existing, incoming) {
      //         return incoming
      //       },
      //     },
      //   },
      // },
    },
  }),
  defaultOptions: {
    watchQuery: {
      errorPolicy: 'all', // Return both data and errors
      fetchPolicy: 'cache-and-network', // Use cache but also fetch fresh data
    },
    query: {
      errorPolicy: 'all',
      fetchPolicy: 'cache-first', // Use cache first, then network
    },
    mutate: {
      errorPolicy: 'all',
    },
  },
  // Enable Apollo DevTools in development
  connectToDevTools: config.env === 'development',
})
