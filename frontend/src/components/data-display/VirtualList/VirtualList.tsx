import React, { ReactNode } from 'react'
import { useVirtualScroll } from '@/hooks/useVirtualScroll'
import { colors } from '@/styles/tokens'
import { cn } from '@/components/utils'

export interface VirtualListProps<T = any> {
  /**
   * Items to render
   */
  items: T[]
  /**
   * Height of each item in pixels
   */
  itemHeight: number
  /**
   * Container height in pixels
   */
  containerHeight: number
  /**
   * Render function for each item
   */
  renderItem: (item: T, index: number) => ReactNode
  /**
   * Key extractor function
   */
  getItemKey?: (item: T, index: number) => string | number
  /**
   * Number of items to render outside visible area
   * @default 3
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
  className?: string
}

/**
 * VirtualList component for efficiently rendering large lists
 *
 * Only renders visible items plus a small overscan buffer.
 * Ideal for lists with hundreds or thousands of items.
 *
 * @example
 * ```tsx
 * <VirtualList
 *   items={users}
 *   itemHeight={50}
 *   containerHeight={400}
 *   renderItem={(user) => <UserCard user={user} />}
 * />
 * ```
 */
export function VirtualList<T = any>({
  items,
  itemHeight,
  containerHeight,
  renderItem,
  getItemKey = (_, index) => index,
  overscan = 3,
  enabled = true,
  emptyComponent,
  loadingComponent,
  isLoading = false,
  className,
}: VirtualListProps<T>) {
  const {
    virtualItems,
    totalHeight,
    containerRef,
    scrollToIndex,
  } = useVirtualScroll(items.length, {
    itemHeight,
    containerHeight,
    overscan,
    enabled,
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
        }}
      >
        {emptyComponent || 'No items'}
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className={cn('virtual-list-container', className)}
      style={{
        height: containerHeight,
        overflow: 'auto',
        position: 'relative',
      }}
    >
      <div
        style={{
          height: totalHeight,
          position: 'relative',
        }}
      >
        {virtualItems.map((virtualItem) => {
          const item = items[virtualItem.index]
          const key = getItemKey(item, virtualItem.index)

          return (
            <div
              key={key}
              style={{
                position: 'absolute',
                top: virtualItem.top,
                left: 0,
                right: 0,
                height: virtualItem.height,
              }}
            >
              {renderItem(item, virtualItem.index)}
            </div>
          )
        })}
      </div>
      {isLoading && loadingComponent && (
        <div
          style={{
            padding: '16px',
            textAlign: 'center',
            borderTop: `1px solid ${colors.semantic.borderDivider}`,
          }}
        >
          {loadingComponent}
        </div>
      )}
    </div>
  )
}

// Expose scrollToIndex for external control
VirtualList.scrollToIndex = (containerRef: React.RefObject<HTMLDivElement>, index: number, itemHeight: number, containerHeight: number) => {
  if (!containerRef.current) return
  const scrollTop = index * itemHeight
  containerRef.current.scrollTop = Math.max(0, scrollTop)
}

VirtualList.displayName = 'VirtualList'

