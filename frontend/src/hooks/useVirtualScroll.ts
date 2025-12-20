import { useState, useEffect, useRef, useMemo, useCallback } from 'react'

export interface UseVirtualScrollOptions {
  /**
   * Height of each item in pixels
   */
  itemHeight: number
  /**
   * Number of items to render outside visible area (overscan)
   * @default 3
   */
  overscan?: number
  /**
   * Container height in pixels (if not provided, will be measured)
   */
  containerHeight?: number
  /**
   * Whether virtual scrolling is enabled
   * @default true
   */
  enabled?: boolean
}

export interface VirtualItem {
  /**
   * Index of the item in the original array
   */
  index: number
  /**
   * Top offset in pixels
   */
  top: number
  /**
   * Height of the item
   */
  height: number
  /**
   * Whether this item is visible
   */
  isVisible: boolean
}

export interface UseVirtualScrollReturn {
  /**
   * Virtual items to render
   */
  virtualItems: VirtualItem[]
  /**
   * Total height of the virtual list
   */
  totalHeight: number
  /**
   * Ref to attach to the scrollable container
   */
  containerRef: React.RefObject<HTMLDivElement>
  /**
   * Scroll to a specific index
   */
  scrollToIndex: (index: number, align?: 'start' | 'center' | 'end') => void
  /**
   * Scroll offset
   */
  scrollOffset: number
}

/**
 * Hook for virtual scrolling functionality
 *
 * Efficiently renders only visible items in a large list.
 *
 * @example
 * ```tsx
 * const { virtualItems, totalHeight, containerRef } = useVirtualScroll({
 *   itemHeight: 50,
 *   itemCount: items.length,
 * })
 *
 * return (
 *   <div ref={containerRef} style={{ height: 400, overflow: 'auto' }}>
 *     <div style={{ height: totalHeight, position: 'relative' }}>
 *       {virtualItems.map(({ index, top }) => (
 *         <div key={index} style={{ position: 'absolute', top, height: 50 }}>
 *           {items[index].name}
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 * )
 * ```
 */
export function useVirtualScroll(
  itemCount: number,
  options: UseVirtualScrollOptions
): UseVirtualScrollReturn {
  const {
    itemHeight,
    overscan = 3,
    containerHeight: initialContainerHeight,
    enabled = true,
  } = options

  const containerRef = useRef<HTMLDivElement>(null)
  const [scrollOffset, setScrollOffset] = useState(0)
  const [containerHeight, setContainerHeight] = useState(
    initialContainerHeight || 0
  )

  // Measure container height if not provided
  useEffect(() => {
    if (initialContainerHeight || !containerRef.current) return

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height)
      }
    })

    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
    }
  }, [initialContainerHeight])

  // Handle scroll events
  useEffect(() => {
    if (!enabled || !containerRef.current) return

    const container = containerRef.current

    const handleScroll = () => {
      setScrollOffset(container.scrollTop)
    }

    container.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll() // Initial calculation

    return () => {
      container.removeEventListener('scroll', handleScroll)
    }
  }, [enabled])

  // Calculate visible range
  const virtualItems = useMemo(() => {
    if (!enabled || itemCount === 0) {
      return []
    }

    const totalHeight = itemCount * itemHeight
    const visibleStart = Math.floor(scrollOffset / itemHeight)
    const visibleEnd = Math.min(
      itemCount - 1,
      Math.ceil((scrollOffset + containerHeight) / itemHeight)
    )

    const start = Math.max(0, visibleStart - overscan)
    const end = Math.min(itemCount - 1, visibleEnd + overscan)

    const items: VirtualItem[] = []
    for (let i = start; i <= end; i++) {
      items.push({
        index: i,
        top: i * itemHeight,
        height: itemHeight,
        isVisible: i >= visibleStart && i <= visibleEnd,
      })
    }

    return items
  }, [enabled, itemCount, itemHeight, scrollOffset, containerHeight, overscan])

  const totalHeight = useMemo(() => {
    return itemCount * itemHeight
  }, [itemCount, itemHeight])

  const scrollToIndex = useCallback(
    (index: number, align: 'start' | 'center' | 'end' = 'start') => {
      if (!containerRef.current) return

      const container = containerRef.current
      let scrollTop = 0

      switch (align) {
        case 'start':
          scrollTop = index * itemHeight
          break
        case 'center':
          scrollTop = index * itemHeight - containerHeight / 2 + itemHeight / 2
          break
        case 'end':
          scrollTop = index * itemHeight - containerHeight + itemHeight
          break
      }

      container.scrollTop = Math.max(0, scrollTop)
    },
    [itemHeight, containerHeight]
  )

  return {
    virtualItems,
    totalHeight,
    containerRef,
    scrollToIndex,
    scrollOffset,
  }
}

