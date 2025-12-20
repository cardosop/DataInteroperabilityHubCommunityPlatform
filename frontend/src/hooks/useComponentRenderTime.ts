/**
 * useComponentRenderTime Hook
 *
 * Hook for tracking component render times to identify performance bottlenecks.
 */

import React, { useEffect, useRef } from 'react'

export interface UseComponentRenderTimeOptions {
  /**
   * Component name (for tracking)
   */
  componentName?: string
  /**
   * Whether tracking is enabled
   * @default true
   */
  enabled?: boolean
  /**
   * Threshold in milliseconds (warn if render time exceeds)
   */
  warnThreshold?: number
  /**
   * Callback when render time is measured
   */
  onRenderTime?: (renderTime: number, componentName: string) => void
}

/**
 * Hook for tracking component render time
 *
 * @param options - Tracking options
 *
 * @example
 * ```tsx
 * function ExpensiveComponent() {
 *   useComponentRenderTime({
 *     componentName: 'ExpensiveComponent',
 *     warnThreshold: 16, // Warn if render takes more than 16ms
 *     onRenderTime: (time) => {
 *       if (time > 16) {
 *         console.warn(`Slow render: ${time}ms`)
 *       }
 *     },
 *   })
 *
 *   return <div>Content</div>
 * }
 * ```
 */
export function useComponentRenderTime(
  options: UseComponentRenderTimeOptions = {}
): void {
  const {
    componentName = 'Unknown',
    enabled = true,
    warnThreshold,
    onRenderTime,
  } = options

  const renderStartRef = useRef<number>(0)
  const isFirstRenderRef = useRef(true)

  useEffect(() => {
    if (!enabled) return

    // Mark render start
    renderStartRef.current = performance.now()

    return () => {
      // Calculate render time
      const renderTime = performance.now() - renderStartRef.current

      // Skip first render (mount time is not meaningful)
      if (isFirstRenderRef.current) {
        isFirstRenderRef.current = false
        return
      }

      // Track render time globally if available
      if (typeof window !== 'undefined' && (window as any).__trackComponentRenderTime) {
        ;(window as any).__trackComponentRenderTime(componentName, renderTime)
      }

      // Call callback
      if (onRenderTime) {
        onRenderTime(renderTime, componentName)
      }

      // Warn if threshold exceeded
      if (warnThreshold && renderTime > warnThreshold) {
        console.warn(
          `[Performance] Slow render detected in ${componentName}: ${renderTime.toFixed(2)}ms (threshold: ${warnThreshold}ms)`
        )
      }

      // Log in development
      if (import.meta.env.DEV && renderTime > 10) {
        console.log(`[Performance] ${componentName} render time: ${renderTime.toFixed(2)}ms`)
      }
    }
  }, [enabled, componentName, warnThreshold, onRenderTime])
}

/**
 * Higher-order component for tracking render time
 *
 * @param Component - Component to wrap
 * @param componentName - Component name
 * @returns Wrapped component with render time tracking
 *
 * @example
 * ```tsx
 * const TrackedComponent = withRenderTimeTracking(ExpensiveComponent, 'ExpensiveComponent')
 * ```
 */
export function withRenderTimeTracking<P extends object>(
  Component: React.ComponentType<P>,
  componentName?: string
): React.ComponentType<P> {
  const WrappedComponent = (props: P) => {
    useComponentRenderTime({
      componentName: componentName || Component.displayName || Component.name || 'Unknown',
      enabled: import.meta.env.DEV || import.meta.env.PROD,
    })

    return React.createElement(Component, props)
  }

  WrappedComponent.displayName = `withRenderTimeTracking(${componentName || Component.displayName || Component.name})`

  return WrappedComponent
}

