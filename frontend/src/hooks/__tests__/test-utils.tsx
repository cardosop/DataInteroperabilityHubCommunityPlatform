/**
 * Test Utilities for Hooks
 *
 * Provides React Query setup for testing hooks.
 */

import { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * Create a test QueryClient with test-friendly defaults
 */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0, // Don't cache in tests
      },
      mutations: {
        retry: false,
      },
    },
  })
}

/**
 * Wrapper component for testing hooks with React Query
 */
export function createHookWrapper(queryClient?: QueryClient) {
  const client = queryClient || createTestQueryClient()

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        {children}
      </QueryClientProvider>
    )
  }
}

