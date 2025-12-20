import React, { Suspense, ComponentType } from 'react'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'

/**
 * Create a lazy-loaded route component with Suspense
 * This is a utility for route-level code splitting
 */
export function createLazyRoute<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  fallback?: React.ReactNode
): React.ComponentType {
  const LazyComponent = React.lazy(importFn)

  const WrappedComponent: React.FC = (props) => {
    return (
      <Suspense
        fallback={
          fallback || <LoadingSpinner fullPage message="Loading page..." />
        }
      >
        <LazyComponent {...props} />
      </Suspense>
    )
  }

  WrappedComponent.displayName = `LazyRoute(${LazyComponent.displayName || 'Component'})`

  return WrappedComponent
}

