/**
 * LazyApolloProvider Component
 *
 * Lazy-loaded wrapper for Apollo Client Provider to enable component-based code splitting.
 * Apollo Client is only needed for GraphQL features and should be loaded on demand.
 */

import React, { Suspense, ReactNode } from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'

// Lazy load Apollo Provider
const ApolloProviderLazy = React.lazy(() =>
  import('@apollo/client').then((module) => ({
    default: module.ApolloProvider,
  }))
)

/**
 * Loading fallback for Apollo Provider
 */
const ApolloProviderFallback: React.FC = () => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      gap: 2,
    }}
  >
    <CircularProgress size={40} />
    <Typography variant="body2" color="text.secondary">
      Loading GraphQL client...
    </Typography>
  </Box>
)

export interface LazyApolloProviderProps {
  /**
   * Apollo Client instance
   */
  client: any
  /**
   * Children to render
   */
  children: ReactNode
  /**
   * Custom fallback component
   */
  fallback?: React.ReactNode
}

/**
 * LazyApolloProvider component
 *
 * Wraps Apollo Provider with lazy loading and Suspense boundary.
 * The Apollo Client chunk will only be loaded when this component is rendered.
 *
 * @example
 * ```tsx
 * <LazyApolloProvider client={apolloClient}>
 *   <GraphQLComponent />
 * </LazyApolloProvider>
 * ```
 */
export const LazyApolloProvider: React.FC<LazyApolloProviderProps> = ({
  client,
  children,
  fallback,
}) => {
  return (
    <Suspense fallback={fallback || <ApolloProviderFallback />}>
      <ApolloProviderLazy client={client}>
        {children}
      </ApolloProviderLazy>
    </Suspense>
  )
}

/**
 * Preload Apollo Client chunk
 * Useful for prefetching the GraphQL client before it's needed
 */
export async function preloadApolloClient(): Promise<void> {
  await import('@apollo/client')
}

