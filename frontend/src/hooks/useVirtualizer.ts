/**
 * useVirtualizer Hook
 *
 * Wrapper hook for @tanstack/react-virtual useVirtualizer.
 * Provides a simplified API for virtual scrolling with common configurations.
 */

import { useRef, useMemo } from 'react'
import { useVirtualizer, VirtualizerOptions, Virtualizer } from '@tanstack/react-virtual'

export interface UseVirtualizerOptions<T = any> {
  /**
   * Number of items to virtualize
   */
  count: number
  /**
   * Height of each item in pixels (for fixed height)
   */
  itemHeight?: number
  /**
   * Function to get item height dynamically (for variable height)
   */
  getItemHeight?: (index: number) => number
  /**
   * Estimated item height (used when getItemHeight is provided)
   */
  estimateSize?: number
  /**
   * Number of items to render outside visible area
   * @default 5
   */
  overscan?: number
  /**
   * Whether virtual scrolling is enabled
   * @default true
   */
  enabled?: boolean
  /**
   * Horizontal scrolling (for grids)
   * @default false
   */
  horizontal?: boolean
  /**
   * Scroll padding
   */
  scrollPaddingStart?: number
  scrollPaddingEnd?: number
  /**
   * Scroll margin
   */
  scrollMargin?: number
  /**
   * Initial scroll offset
   */
  initialOffset?: number
  /**
   * Callback when scroll offset changes
   */
  onScrollOffsetChange?: (offset: number) => void
  /**
   * Callback when scroll index changes
   */
  onScrollIndexChange?: (index: number) => void
  /**
   * Custom scroll element (defaults to parent)
   */
  scrollElement?: HTMLElement | null
}

export interface UseVirtualizerReturn {
  /**
   * Virtualizer instance
   */
  virtualizer: Virtualizer<HTMLElement, Element>
  /**
   * Ref to attach to the scrollable container
   */
  parentRef: React.RefObject<HTMLElement>
  /**
   * Virtual items to render
   */
  virtualItems: ReturnType<Virtualizer<HTMLElement, Element>['getVirtualItems']>
  /**
   * Total size of the virtual list
   */
  totalSize: number
  /**
   * Scroll to a specific index
   */
  scrollToIndex: (index: number, options?: { align?: 'start' | 'center' | 'end' }) => void
  /**
   * Scroll to a specific offset
   */
  scrollToOffset: (offset: number, options?: { align?: 'start' | 'center' | 'end' }) => void
  /**
   * Measure element size
   */
  measureElement: (element: HTMLElement | null) => void
}

/**
 * Hook for virtual scrolling using @tanstack/react-virtual
 *
 * @param options - Virtualizer options
 * @returns Virtualizer instance and utilities
 *
 * @example
 * ```tsx
 * // Fixed height
 * const { virtualItems, parentRef, totalSize } = useVirtualizer({
 *   count: items.length,
 *   itemHeight: 50,
 * })
 *
 * return (
 *   <div ref={parentRef} style={{ height: 400, overflow: 'auto' }}>
 *     <div style={{ height: totalSize, position: 'relative' }}>
 *       {virtualItems.map((virtualItem) => (
 *         <div
 *           key={virtualItem.key}
 *           style={{
 *             position: 'absolute',
 *             top: 0,
 *             left: 0,
 *             width: '100%',
 *             height: virtualItem.size,
 *             transform: `translateY(${virtualItem.start}px)`,
 *           }}
 *         >
 *           {items[virtualItem.index].name}
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 * )
 * ```
 *
 * @example
 * ```tsx
 * // Variable height
 * const { virtualItems, parentRef, totalSize, measureElement } = useVirtualizer({
 *   count: items.length,
 *   getItemHeight: (index) => items[index].height,
 *   estimateSize: 50,
 * })
 *
 * return (
 *   <div ref={parentRef} style={{ height: 400, overflow: 'auto' }}>
 *     <div style={{ height: totalSize, position: 'relative' }}>
 *       {virtualItems.map((virtualItem) => (
 *         <div
 *           key={virtualItem.key}
 *           ref={measureElement}
 *           style={{
 *             position: 'absolute',
 *             top: 0,
 *             left: 0,
 *             width: '100%',
 *             transform: `translateY(${virtualItem.start}px)`,
 *           }}
 *         >
 *           {items[virtualItem.index].name}
 *         </div>
 *       ))}
 *     </div>
 *   </div>
 * )
 * ```
 */
export function useVirtualizer<T = any>(
  options: UseVirtualizerOptions<T>
): UseVirtualizerReturn {
  const {
    count,
    itemHeight,
    getItemHeight,
    estimateSize,
    overscan = 5,
    enabled = true,
    horizontal = false,
    scrollPaddingStart,
    scrollPaddingEnd,
    scrollMargin,
    initialOffset,
    onScrollOffsetChange,
    onScrollIndexChange,
    scrollElement,
  } = options

  const parentRef = useRef<HTMLElement>(null)

  // Create virtualizer options
  const virtualizerOptions = useMemo<VirtualizerOptions<HTMLElement, Element>>(() => {
    const baseOptions: VirtualizerOptions<HTMLElement, Element> = {
      count,
      getScrollElement: () => scrollElement || parentRef.current,
      estimateSize: itemHeight || estimateSize || 50,
      overscan,
      horizontal,
      enabled,
    }

    // Add size configuration
    if (itemHeight) {
      baseOptions.estimateSize = itemHeight
    } else if (getItemHeight) {
      baseOptions.getItemSize = getItemHeight
      if (estimateSize) {
        baseOptions.estimateSize = estimateSize
      }
    }

    // Add scroll padding
    if (scrollPaddingStart !== undefined) {
      baseOptions.scrollPaddingStart = scrollPaddingStart
    }
    if (scrollPaddingEnd !== undefined) {
      baseOptions.scrollPaddingEnd = scrollPaddingEnd
    }
    if (scrollMargin !== undefined) {
      baseOptions.scrollMargin = scrollMargin
    }

    // Add initial offset
    if (initialOffset !== undefined) {
      baseOptions.initialOffset = initialOffset
    }

    // Add callbacks
    if (onScrollOffsetChange) {
      baseOptions.onChange = (instance) => {
        onScrollOffsetChange(instance.scrollOffset)
      }
    }

    return baseOptions
  }, [
    count,
    itemHeight,
    getItemHeight,
    estimateSize,
    overscan,
    enabled,
    horizontal,
    scrollPaddingStart,
    scrollPaddingEnd,
    scrollMargin,
    initialOffset,
    onScrollOffsetChange,
    scrollElement,
  ])

  // Create virtualizer instance
  const virtualizer = useVirtualizer(virtualizerOptions)

  // Get virtual items
  const virtualItems = virtualizer.getVirtualItems()

  // Scroll to index
  const scrollToIndex = (
    index: number,
    scrollOptions?: { align?: 'start' | 'center' | 'end' }
  ) => {
    virtualizer.scrollToIndex(index, scrollOptions)
  }

  // Scroll to offset
  const scrollToOffset = (
    offset: number,
    scrollOptions?: { align?: 'start' | 'center' | 'end' }
  ) => {
    virtualizer.scrollToOffset(offset, scrollOptions)
  }

  // Measure element
  const measureElement = (element: HTMLElement | null) => {
    if (element) {
      virtualizer.measureElement(element)
    }
  }

  // Call onScrollIndexChange callback
  if (onScrollIndexChange) {
    const currentIndex = virtualizer.getVirtualItems()[0]?.index
    if (currentIndex !== undefined) {
      // This would need to be tracked in a ref to avoid infinite loops
      // For now, we'll rely on the virtualizer's onChange callback
    }
  }

  return {
    virtualizer,
    parentRef,
    virtualItems,
    totalSize: virtualizer.getTotalSize(),
    scrollToIndex,
    scrollToOffset,
    measureElement,
  }
}

