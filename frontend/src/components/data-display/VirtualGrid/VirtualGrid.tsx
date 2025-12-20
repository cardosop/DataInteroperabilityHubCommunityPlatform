/**
 * VirtualGrid Component
 *
 * Virtual grid component using @tanstack/react-virtual for efficient rendering
 * of large grids. Only renders visible items plus an overscan buffer.
 */

import React, { ReactNode } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { colors, spacing } from '@/styles/tokens'
import { cn } from '@/components/utils'

export interface VirtualGridProps<T = any> {
  /**
   * Items to render
   */
  items: T[]
  /**
   * Number of columns
   */
  columns: number
  /**
   * Height of each row in pixels
   */
  rowHeight?: number
  /**
   * Function to get row height dynamically (for variable height)
   */
  getRowHeight?: (index: number) => number
  /**
   * Estimated row height (used when getRowHeight is provided)
   */
  estimateRowHeight?: number
  /**
   * Container height in pixels
   */
  containerHeight: number
  /**
   * Container width in pixels (defaults to 100%)
   */
  containerWidth?: number | string
  /**
   * Gap between grid items
   * @default 8
   */
  gap?: number
  /**
   * Render function for each item
   */
  renderItem: (item: T, index: number, row: number, col: number) => ReactNode
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
}

/**
 * VirtualGrid component for efficiently rendering large grids
 *
 * Uses @tanstack/react-virtual to only render visible rows plus an overscan buffer.
 * Ideal for grids with hundreds or thousands of items.
 *
 * @example
 * ```tsx
 * <VirtualGrid
 *   items={products}
 *   columns={3}
 *   rowHeight={200}
 *   containerHeight={600}
 *   gap={16}
 *   renderItem={(product, index, row, col) => (
 *     <ProductCard product={product} />
 *   )}
 *   getItemKey={(product) => product.id}
 * />
 * ```
 */
export function VirtualGrid<T = any>({
  items,
  columns,
  rowHeight,
  getRowHeight,
  estimateRowHeight,
  containerHeight,
  containerWidth = '100%',
  gap = 8,
  renderItem,
  getItemKey = (_, index) => index,
  overscan = 5,
  enabled = true,
  emptyComponent,
  loadingComponent,
  isLoading = false,
  className,
  style,
}: VirtualGridProps<T>) {
  const parentRef = React.useRef<HTMLDivElement>(null)

  // Calculate number of rows
  const rowCount = Math.ceil(items.length / columns)

  // Create row virtualizer
  const rowVirtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: rowHeight || estimateRowHeight || 200,
    getItemSize: getRowHeight,
    overscan,
    enabled,
  })

  const virtualRows = rowVirtualizer.getVirtualItems()
  const totalSize = rowVirtualizer.getTotalSize()

  if (items.length === 0) {
    return (
      <div
        className={cn('virtual-grid-empty', className)}
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
      ref={parentRef}
      className={cn('virtual-grid-container', className)}
      style={{
        height: containerHeight,
        width: containerWidth,
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
        {virtualRows.map((virtualRow) => {
          const rowStart = virtualRow.index * columns
          const rowEnd = Math.min(rowStart + columns, items.length)
          const rowItems = items.slice(rowStart, rowEnd)

          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: virtualRow.size,
                transform: `translateY(${virtualRow.start}px)`,
                display: 'grid',
                gridTemplateColumns: `repeat(${columns}, 1fr)`,
                gap: `${gap}px`,
                padding: `0 ${gap / 2}px`,
              }}
            >
              {rowItems.map((item, colIndex) => {
                const index = rowStart + colIndex
                const key = getItemKey(item, index)

                return (
                  <div key={key} style={{ width: '100%' }}>
                    {renderItem(item, index, virtualRow.index, colIndex)}
                  </div>
                )
              })}
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

VirtualGrid.displayName = 'VirtualGrid'

