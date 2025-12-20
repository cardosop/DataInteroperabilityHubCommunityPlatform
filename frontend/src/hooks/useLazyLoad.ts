/**
 * useLazyLoad Hook
 *
 * Hook for lazy loading components when they enter the viewport.
 * Uses Intersection Observer for efficient visibility detection.
 */

import { useState, useEffect, RefObject } from 'react'
import { useIntersectionObserver } from './useIntersectionObserver'

export interface UseLazyLoadOptions {
  /**
   * Whether lazy loading is enabled
   * @default true
   */
  enabled?: boolean
  /**
   * Root margin for Intersection Observer
   * @default '50px'
   */
  rootMargin?: string
  /**
   * Threshold for intersection
   * @default 0
   */
  threshold?: number | number[]
  /**
   * Root element for intersection observer
   */
  root?: Element | null
  /**
   * Whether to load only once
   * @default true
   */
  once?: boolean
}

export interface UseLazyLoadReturn {
  /**
   * Whether the component should be loaded
   */
  shouldLoad: boolean
  /**
   * Whether the element is intersecting
   */
  isIntersecting: boolean
  /**
   * Ref to attach to the element
   */
  ref: RefObject<HTMLElement>
}

/**
 * Hook for lazy loading components
 *
 * @param options - Lazy load options
 * @returns Lazy load state and ref
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { shouldLoad, ref } = useLazyLoad()
 *
 *   return (
 *     <div ref={ref}>
 *       {shouldLoad ? <HeavyComponent /> : <Placeholder />}
 *     </div>
 *   )
 * }
 * ```
 *
 * @example
 * ```tsx
 * // With custom root margin
 * const { shouldLoad, ref } = useLazyLoad({
 *   rootMargin: '100px',
 *   once: true,
 * })
 * ```
 */
export function useLazyLoad(
  options: UseLazyLoadOptions = {}
): UseLazyLoadReturn {
  const {
    enabled = true,
    rootMargin = '50px',
    threshold = 0,
    root = null,
    once = true,
  } = options

  const { isIntersecting, ref } = useIntersectionObserver({
    enabled,
    rootMargin,
    threshold,
    root,
    once,
  })

  const [shouldLoad, setShouldLoad] = useState(!enabled)

  useEffect(() => {
    if (!enabled) {
      setShouldLoad(true)
      return
    }

    if (isIntersecting) {
      setShouldLoad(true)
    }
  }, [enabled, isIntersecting])

  return {
    shouldLoad,
    isIntersecting,
    ref,
  }
}

