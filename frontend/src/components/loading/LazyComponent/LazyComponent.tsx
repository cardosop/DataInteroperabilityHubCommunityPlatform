import React, { Suspense, ComponentType, LazyExoticComponent } from 'react'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'

export interface LazyComponentProps {
  /**
   * Lazy-loaded component
   */
  component: LazyExoticComponent<ComponentType<any>> | ComponentType<any>
  /**
   * Fallback component (shown while loading)
   */
  fallback?: React.ReactNode
  /**
   * Props to pass to the component
   */
  componentProps?: Record<string, any>
}

/**
 * LazyComponent wrapper for lazy-loaded components with Suspense
 */
export const LazyComponent: React.FC<LazyComponentProps> = ({
  component: Component,
  fallback = <LoadingSpinner message="Loading component..." />,
  componentProps = {},
}) => {
  return (
    <Suspense fallback={fallback}>
      <Component {...componentProps} />
    </Suspense>
  )
}

LazyComponent.displayName = 'LazyComponent'

/**
 * Utility function to create a lazy component with default loading fallback
 */
export function createLazyComponent<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>
): LazyExoticComponent<T> {
  return React.lazy(importFn)
}

