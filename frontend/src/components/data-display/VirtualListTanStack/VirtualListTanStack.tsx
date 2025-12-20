/**
 * VirtualListTanStack Component
 *
 * Virtual list component using @tanstack/react-virtual for efficient rendering
 * of large lists. Only renders visible items plus an overscan buffer.
 */

import React, { ReactNode } from 'react'
import { useVirtualizer } from '@/hooks/useVirtualizer'
import { colors, spacing } from '@/styles/tokens'
import { cn } from '@/components/utils'

export interface VirtualListTanStackProps<T = any> {
  /**
   * Items to render
   */
  items: T[]
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
   * Container height in pixels
   */
  containerHeight: number
  /**
   * Render function for each item
   */
  renderItem: (item: T, index: number, virtualItem: any) => ReactNode
  /**
   * Key extractor function
   */
  getItemKey?: (item: T, index: number) => string | number
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
   * Empty state component
   */
  emptyComponent?: ReactNode
  /**
   * Loading component (shown at bottom when loading)
   */
  loadingComponent?: ReactNode
  /**
   * Whether data is loading
   */
  isLoading?: boolean
  /**
   * Custom className
   */
  className?: string
  /**
   * Custom style
   */
  style?: React.CSSProperties
  /**
   * Scroll padding
   */
  scrollPaddingStart?: number
  scrollPaddingEnd?: number
  /**
   * Scroll margin
   */
  scrollMargin?: number
}

/**
 * VirtualListTanStack component for efficiently rendering large lists
 *
 * Uses @tanstack/react-virtual to only render visible items plus an overscan buffer.
 * Ideal for lists with hundreds or thousands of items.
 *
 * @example
 * ```tsx
 * <VirtualListTanStack
 *   items={users}
 *   itemHeight={50}
 *   containerHeight={400}
 *   renderItem={(user, index, virtualItem) => (
 *     <div style={{ padding: '12px', borderBottom: '1px solid #eee' }}>
 *       {user.name}
 *     </div>
 *   )}
 *   getItemKey={(user) => user.id}
 * />
 * ```
 *
 * @example
 * ```tsx
 * // Variable height
 * <VirtualListTanStack
 *   items={items}
 *   getItemHeight={(index) => items[index].height}
 *   estimateSize={50}
 *   containerHeight={400}
 *   renderItem={(item, index, virtualItem) => (
 *     <div ref={virtualItem.measureElement}>
 *       {item.content}
 *     </div>
 *   )}
 * />
 * ```
 */
export function VirtualListTanStack<T = any>({
  items,
  itemHeight,
  getItemHeight,
  estimateSize,
  containerHeight,
  renderItem,
  getItemKey = (_, index) => index,
  overscan = 5,
  enabled = true,
  emptyComponent,
  loadingComponent,
  isLoading = false,
  className,
  style,
  scrollPaddingStart,
  scrollPaddingEnd,
  scrollMargin,
}: VirtualListTanStackProps<T>) {
  const {
    virtualItems,
    parentRef,
    totalSize,
    measureElement,
  } = useVirtualizer({
    count: items.length,
    itemHeight,
    getItemHeight,
    estimateSize,
    overscan,
    enabled,
    scrollPaddingStart,
    scrollPaddingEnd,
    scrollMargin,
  })

  if (items.length === 0) {
    return (
      <div
        className={cn('virtual-list-empty', className)}
        style={{
          height: containerHeight,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: colors.semantic.textSecondary,
          ...style,
        }}
      >
        {emptyComponent || 'No items'}
      </div>
    )
  }

  return (
    <div
      ref={parentRef as React.RefObject<HTMLDivElement>}
      className={cn('virtual-list-container', className)}
      style={{
        height: containerHeight,
        overflow: 'auto',
        ...style,
      }}
    >
      <div
        style={{
          height: totalSize,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualItems.map((virtualItem) => {
          const item = items[virtualItem.index]
          const key = getItemKey(item, virtualItem.index)

          return (
            <div
              key={key}
              data-index={virtualItem.index}
              ref={getItemHeight ? measureElement : undefined}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: itemHeight ? itemHeight : undefined,
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              {renderItem(item, virtualItem.index, virtualItem)}
            </div>
          )
        })}
      </div>
      {isLoading && loadingComponent && (
        <div
          style={{
            padding: spacing[2],
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}
        >
          {loadingComponent}
        </div>
      )}
    </div>
  )
}

VirtualListTanStack.displayName = 'VirtualListTanStack'

