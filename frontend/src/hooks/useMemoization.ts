/**
 * Memoization Hooks
 *
 * Custom hooks for common memoization patterns.
 */

import { useMemo, useCallback, DependencyList } from 'react'
import {
  useMemoizedValue,
  useMemoizedCallback,
  useMemoizedObject,
  useMemoizedArray,
  useMemoizedFilter,
  useMemoizedMap,
  useMemoizedSort,
  useMemoizedReduce,
  useMemoizedDebounce,
  useMemoizedThrottle,
} from '@/utils/memoization'

// Re-export utilities as hooks for consistency
export {
  useMemoizedValue,
  useMemoizedCallback,
  useMemoizedObject,
  useMemoizedArray,
  useMemoizedFilter,
  useMemoizedMap,
  useMemoizedSort,
  useMemoizedReduce,
  useMemoizedDebounce,
  useMemoizedThrottle,
}

/**
 * Hook to memoize a computed value with automatic dependency tracking
 *
 * @param factory - Function that computes the value
 * @param deps - Dependency array
 * @returns Memoized computed value
 *
 * @example
 * ```tsx
 * const expensiveValue = useComputed(() => {
 *   return items.reduce((sum, item) => sum + item.value, 0)
 * }, [items])
 * ```
 */
export function useComputed<T>(
  factory: () => T,
  deps: DependencyList
): T {
  return useMemoizedValue(factory, deps)
}

/**
 * Hook to memoize an event handler
 *
 * @param handler - Event handler function
 * @param deps - Dependency array
 * @returns Memoized event handler
 *
 * @example
 * ```tsx
 * const handleClick = useEventHandler((id: string) => {
 *   console.log('Clicked:', id)
 * }, [])
 * ```
 */
export function useEventHandler<T extends (...args: any[]) => any>(
  handler: T,
  deps: DependencyList
): T {
  return useMemoizedCallback(handler, deps)
}

/**
 * Hook to memoize a stable object reference
 * Useful when passing objects as props to memoized components
 *
 * @param obj - Object to memoize
 * @param deps - Dependency array (values that affect the object)
 * @returns Memoized object with stable reference
 *
 * @example
 * ```tsx
 * const config = useStableObject(
 *   { theme, size },
 *   [theme, size]
 * )
 * ```
 */
export function useStableObject<T extends Record<string, any>>(
  obj: T,
  deps: DependencyList
): T {
  return useMemoizedObject(obj, deps)
}

/**
 * Hook to memoize a stable array reference
 * Useful when passing arrays as props to memoized components
 *
 * @param arr - Array to memoize
 * @param deps - Dependency array (values that affect the array)
 * @returns Memoized array with stable reference
 *
 * @example
 * ```tsx
 * const items = useStableArray(
 *   [item1, item2, item3],
 *   [item1, item2, item3]
 * )
 * ```
 */
export function useStableArray<T>(
  arr: T[],
  deps: DependencyList
): T[] {
  return useMemoizedArray(arr, deps)
}

