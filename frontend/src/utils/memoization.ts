/**
 * Memoization Utilities
 *
 * Utilities and patterns for implementing React memoization:
 * - React.memo for expensive components
 * - useMemo for expensive computations
 * - useCallback for event handlers
 */

import React, { useMemo, useCallback, DependencyList, ComponentType } from 'react'

/**
 * Custom comparison function type for React.memo
 */
export type ComparisonFunction<T> = (prevProps: T, nextProps: T) => boolean

/**
 * Shallow comparison function for props
 * Useful for React.memo when props are objects/arrays
 */
export function shallowEqual<T extends Record<string, any>>(
  prevProps: T,
  nextProps: T
): boolean {
  const prevKeys = Object.keys(prevProps)
  const nextKeys = Object.keys(nextProps)

  if (prevKeys.length !== nextKeys.length) {
    return false
  }

  for (const key of prevKeys) {
    if (prevProps[key] !== nextProps[key]) {
      return false
    }
  }

  return true
}

/**
 * Deep comparison function for props (use with caution - can be expensive)
 * Only use when shallow comparison is insufficient
 */
export function deepEqual<T>(a: T, b: T): boolean {
  if (a === b) return true
  if (a == null || b == null) return false
  if (typeof a !== 'object' || typeof b !== 'object') return false

  const keysA = Object.keys(a as Record<string, any>)
  const keysB = Object.keys(b as Record<string, any>)

  if (keysA.length !== keysB.length) return false

  for (const key of keysA) {
    if (!keysB.includes(key)) return false
    if (!deepEqual((a as Record<string, any>)[key], (b as Record<string, any>)[key])) {
      return false
    }
  }

  return true
}

/**
 * Create a memoized component with custom comparison
 *
 * @param Component - Component to memoize
 * @param areEqual - Custom comparison function (optional)
 * @returns Memoized component
 *
 * @example
 * ```tsx
 * const MemoizedCard = createMemoizedComponent(Card, shallowEqual)
 * ```
 */
export function createMemoizedComponent<P extends object>(
  Component: ComponentType<P>,
  areEqual?: ComparisonFunction<P>
): React.MemoExoticComponent<ComponentType<P>> {
  const MemoizedComponent = React.memo(Component, areEqual)
  // Set displayName for better debugging
  MemoizedComponent.displayName = `Memo(${Component.displayName || Component.name || 'Component'})`
  return MemoizedComponent
}

/**
 * Memoize a value with dependency tracking
 * Wrapper around useMemo with better TypeScript support
 *
 * @param factory - Function that returns the value
 * @param deps - Dependency array
 * @returns Memoized value
 *
 * @example
 * ```tsx
 * const sortedItems = useMemoizedValue(
 *   () => items.sort((a, b) => a.name.localeCompare(b.name)),
 *   [items]
 * )
 * ```
 */
export function useMemoizedValue<T>(
  factory: () => T,
  deps: DependencyList
): T {
  return useMemo(factory, deps)
}

/**
 * Memoize a callback function
 * Wrapper around useCallback with better TypeScript support
 *
 * @param callback - Callback function
 * @param deps - Dependency array
 * @returns Memoized callback
 *
 * @example
 * ```tsx
 * const handleClick = useMemoizedCallback(
 *   (id: string) => {
 *     console.log('Clicked:', id)
 *   },
 *   []
 * )
 * ```
 */
export function useMemoizedCallback<T extends (...args: any[]) => any>(
  callback: T,
  deps: DependencyList
): T {
  return useCallback(callback, deps) as T
}

/**
 * Memoize an object to prevent unnecessary re-renders
 * Useful when passing objects as props
 *
 * @param obj - Object to memoize
 * @param deps - Dependency array
 * @returns Memoized object
 *
 * @example
 * ```tsx
 * const config = useMemoizedObject(
 *   { theme: 'dark', size: 'large' },
 *   [theme, size]
 * )
 * ```
 */
export function useMemoizedObject<T extends Record<string, any>>(
  obj: T,
  deps: DependencyList
): T {
  return useMemo(() => obj, deps)
}

/**
 * Memoize an array to prevent unnecessary re-renders
 * Useful when passing arrays as props
 *
 * @param arr - Array to memoize
 * @param deps - Dependency array
 * @returns Memoized array
 *
 * @example
 * ```tsx
 * const items = useMemoizedArray(
 *   [1, 2, 3],
 *   [dependency1, dependency2]
 * )
 * ```
 */
export function useMemoizedArray<T>(
  arr: T[],
  deps: DependencyList
): T[] {
  return useMemo(() => arr, deps)
}

/**
 * Memoize a filtered array
 * Combines filtering and memoization
 *
 * @param items - Array to filter
 * @param filterFn - Filter function
 * @param deps - Dependency array (should include items and filter dependencies)
 * @returns Memoized filtered array
 *
 * @example
 * ```tsx
 * const activeUsers = useMemoizedFilter(
 *   users,
 *   (user) => user.active,
 *   [users]
 * )
 * ```
 */
export function useMemoizedFilter<T>(
  items: T[],
  filterFn: (item: T) => boolean,
  deps: DependencyList
): T[] {
  return useMemo(() => items.filter(filterFn), [items, filterFn, ...deps])
}

/**
 * Memoize a mapped array
 * Combines mapping and memoization
 *
 * @param items - Array to map
 * @param mapFn - Map function
 * @param deps - Dependency array (should include items and map dependencies)
 * @returns Memoized mapped array
 *
 * @example
 * ```tsx
 * const userNames = useMemoizedMap(
 *   users,
 *   (user) => user.name,
 *   [users]
 * )
 * ```
 */
export function useMemoizedMap<T, U>(
  items: T[],
  mapFn: (item: T) => U,
  deps: DependencyList
): U[] {
  return useMemo(() => items.map(mapFn), [items, mapFn, ...deps])
}

/**
 * Memoize a sorted array
 * Combines sorting and memoization
 *
 * @param items - Array to sort
 * @param compareFn - Compare function
 * @param deps - Dependency array (should include items and sort dependencies)
 * @returns Memoized sorted array
 *
 * @example
 * ```tsx
 * const sortedUsers = useMemoizedSort(
 *   users,
 *   (a, b) => a.name.localeCompare(b.name),
 *   [users]
 * )
 * ```
 */
export function useMemoizedSort<T>(
  items: T[],
  compareFn: (a: T, b: T) => number,
  deps: DependencyList
): T[] {
  return useMemo(() => [...items].sort(compareFn), [items, compareFn, ...deps])
}

/**
 * Memoize a reduced value
 * Combines reduction and memoization
 *
 * @param items - Array to reduce
 * @param reduceFn - Reduce function
 * @param initialValue - Initial value
 * @param deps - Dependency array (should include items and reduce dependencies)
 * @returns Memoized reduced value
 *
 * @example
 * ```tsx
 * const total = useMemoizedReduce(
 *   items,
 *   (sum, item) => sum + item.price,
 *   0,
 *   [items]
 * )
 * ```
 */
export function useMemoizedReduce<T, U>(
  items: T[],
  reduceFn: (acc: U, item: T) => U,
  initialValue: U,
  deps: DependencyList
): U {
  return useMemo(
    () => items.reduce(reduceFn, initialValue),
    [items, reduceFn, initialValue, ...deps]
  )
}

/**
 * Memoize a debounced callback
 * Useful for search inputs, resize handlers, etc.
 *
 * @param callback - Callback to debounce
 * @param delay - Debounce delay in milliseconds
 * @param deps - Dependency array
 * @returns Memoized debounced callback
 *
 * @example
 * ```tsx
 * const debouncedSearch = useMemoizedDebounce(
 *   (query: string) => {
 *     performSearch(query)
 *   },
 *   300,
 *   []
 * )
 * ```
 */
export function useMemoizedDebounce<T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
  deps: DependencyList
): T {
  const timeoutRef = React.useRef<NodeJS.Timeout>()

  return useMemoizedCallback(
    ((...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
      timeoutRef.current = setTimeout(() => {
        callback(...args)
      }, delay)
    }) as T,
    [callback, delay, ...deps]
  )
}

/**
 * Memoize a throttled callback
 * Useful for scroll handlers, mouse move handlers, etc.
 *
 * @param callback - Callback to throttle
 * @param delay - Throttle delay in milliseconds
 * @param deps - Dependency array
 * @returns Memoized throttled callback
 *
 * @example
 * ```tsx
 * const throttledScroll = useMemoizedThrottle(
 *   (event: Event) => {
 *     handleScroll(event)
 *   },
 *   100,
 *   []
 * )
 * ```
 */
export function useMemoizedThrottle<T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
  deps: DependencyList
): T {
  const lastRunRef = React.useRef<number>(0)

  return useMemoizedCallback(
    ((...args: Parameters<T>) => {
      const now = Date.now()
      if (now - lastRunRef.current >= delay) {
        lastRunRef.current = now
        callback(...args)
      }
    }) as T,
    [callback, delay, ...deps]
  )
}

/**
 * HOC to memoize a component with shallow comparison
 *
 * @param Component - Component to memoize
 * @returns Memoized component
 *
 * @example
 * ```tsx
 * const MemoizedCard = withShallowMemo(Card)
 * ```
 */
export function withShallowMemo<P extends object>(
  Component: ComponentType<P>
): React.MemoExoticComponent<ComponentType<P>> {
  return React.memo(Component, shallowEqual)
}

/**
 * HOC to memoize a component with deep comparison (use with caution)
 *
 * @param Component - Component to memoize
 * @returns Memoized component
 *
 * @example
 * ```tsx
 * const MemoizedComplexCard = withDeepMemo(ComplexCard)
 * ```
 */
export function withDeepMemo<P extends object>(
  Component: ComponentType<P>
): React.MemoExoticComponent<ComponentType<P>> {
  return React.memo(Component, deepEqual)
}

