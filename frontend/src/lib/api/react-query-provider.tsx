/**
 * React Query Provider Component
 *
 * Wrapper component that provides QueryClient to the React component tree.
 * This should be placed at the root of your application.
 */

import React, { lazy, Suspense } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './react-query'
import { config } from '@/lib/config'

// Lazy load DevTools to avoid including in production bundle
const ReactQueryDevtools = lazy(() =>
  import('@tanstack/react-query-devtools').then((d) => ({
    default: d.ReactQueryDevtools,
  }))
)

export interface ReactQueryProviderProps {
  /**
   * Children to render
   */
  children: React.ReactNode
  /**
   * Custom QueryClient instance (optional, uses default if not provided)
   */
  client?: typeof queryClient
  /**
   * Show React Query DevTools
   * @default true in development
   */
  showDevtools?: boolean
}

/**
 * React Query Provider component
 *
 * Provides QueryClient to all child components.
 * Includes React Query DevTools in development mode.
 *
 * @example
 * ```tsx
 * <ReactQueryProvider>
 *   <App />
 * </ReactQueryProvider>
 * ```
 */
export const ReactQueryProvider: React.FC<ReactQueryProviderProps> = ({
  children,
  client = queryClient,
  showDevtools = config.env === 'development' && config.development.enableReactQueryDevtools,
}) => {
  return (
    <QueryClientProvider client={client}>
      {children}
      {showDevtools && (
        <Suspense fallback={null}>
          <ReactQueryDevtools
            initialIsOpen={false}
            position="bottom-right"
            buttonPosition="bottom-right"
          />
        </Suspense>
      )}
    </QueryClientProvider>
  )
}

ReactQueryProvider.displayName = 'ReactQueryProvider'

