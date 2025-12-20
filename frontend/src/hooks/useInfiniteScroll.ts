import { useEffect, useRef, useCallback, useState } from 'react'
import { useIntersectionObserver } from './useIntersectionObserver'

export interface UseInfiniteScrollOptions {
  /**
   * Whether infinite scroll is enabled
   * @default true
   */
  enabled?: boolean
  /**
   * Distance from bottom to trigger load (in pixels)
   * @default 100
   */
  threshold?: number
  /**
   * Root element for intersection observer (defaults to window)
   */
  root?: Element | null
  /**
   * Root margin for intersection observer
   */
  rootMargin?: string
  /**
   * Whether there is more data to load
   * @default true
   */
  hasMore?: boolean
  /**
   * Whether data is currently loading
   * @default false
   */
  isLoading?: boolean
}

export interface UseInfiniteScrollReturn {
  /**
   * Ref to attach to the scrollable container or sentinel element
   */
  sentinelRef: React.RefObject<HTMLDivElement>
  /**
   * Whether the sentinel is visible (near bottom)
   */
  isNearBottom: boolean
}

/**
 * Hook for infinite scroll functionality
 *
 * Triggers onLoadMore when user scrolls near the bottom of the container.
 *
 * @example
 * ```tsx
 * const { sentinelRef } = useInfiniteScroll({
 *   onLoadMore: () => fetchNextPage(),
 *   hasMore: hasNextPage,
 *   isLoading: isFetching,
 * })
 *
 * return (
 *   <div>
 *     {items.map(item => <Item key={item.id} {...item} />)}
 *     <div ref={sentinelRef} />
 *     {isLoading && <Loading />}
 *   </div>
 * )
 * ```
 */
export function useInfiniteScroll(
  onLoadMore: () => void | Promise<void>,
  options: UseInfiniteScrollOptions = {}
): UseInfiniteScrollReturn {
  const {
    enabled = true,
    threshold = 100,
    root = null,
    rootMargin,
    hasMore = true,
    isLoading = false,
  } = options

  const sentinelRef = useRef<HTMLDivElement>(null)
  const loadingRef = useRef(false)

  const handleLoadMore = useCallback(async () => {
    if (loadingRef.current || !hasMore || isLoading) return

    loadingRef.current = true
    try {
      await onLoadMore()
    } finally {
      // Small delay to prevent rapid firing
      setTimeout(() => {
        loadingRef.current = false
      }, 100)
    }
  }, [onLoadMore, hasMore, isLoading])

  // Use intersection observer hook for better performance and reusability
  const intersectionObserver = useIntersectionObserver({
    enabled,
    root,
    rootMargin: rootMargin || `${threshold}px`,
    threshold: 0.1,
  })

  // Sync sentinel ref with intersection observer ref
  useEffect(() => {
    if (sentinelRef.current && intersectionObserver.ref.current === null) {
      ;(intersectionObserver.ref as any).current = sentinelRef.current
    }
  }, [intersectionObserver.ref])

  const isNearBottom = intersectionObserver.isIntersecting

  // Trigger load more when sentinel is visible
  useEffect(() => {
    if (isNearBottom && hasMore && !isLoading && !loadingRef.current) {
      handleLoadMore()
    }
  }, [isNearBottom, hasMore, isLoading, handleLoadMore])

  // Fallback: scroll event listener for older browsers or custom containers
  useEffect(() => {
    if (!enabled || root) return // Skip if using Intersection Observer with custom root

    const handleScroll = () => {
      if (loadingRef.current || !hasMore || isLoading) return

      const scrollElement = root || window
      const scrollTop =
        'scrollTop' in scrollElement
          ? scrollElement.scrollTop
          : window.scrollY || document.documentElement.scrollTop
      const scrollHeight =
        'scrollHeight' in scrollElement
          ? scrollElement.scrollHeight
          : document.documentElement.scrollHeight
      const clientHeight =
        'clientHeight' in scrollElement
          ? scrollElement.clientHeight
          : window.innerHeight

      const distanceFromBottom = scrollHeight - scrollTop - clientHeight

      if (distanceFromBottom < threshold) {
        handleLoadMore()
      }
    }

    const scrollContainer = root || window
    scrollContainer.addEventListener('scroll', handleScroll, { passive: true })

    return () => {
      scrollContainer.removeEventListener('scroll', handleScroll)
    }
  }, [enabled, root, threshold, hasMore, isLoading, handleLoadMore])

  return {
    sentinelRef,
    isNearBottom,
  }
}

