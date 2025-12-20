import React from 'react'
import { Pagination, PaginationProps } from './Pagination'
import { PageSizeSelector, PageSizeSelectorProps } from './PageSizeSelector'
import { Stack } from '@/components/layout'
import { colors, spacing } from '@/styles/tokens'
import { cn } from '@/components/utils'

export interface EnhancedPaginationProps extends PaginationProps {
  /**
   * Current page size
   */
  pageSize: number
  /**
   * Available page size options
   */
  pageSizeOptions?: number[]
  /**
   * Callback when page size changes
   */
  onPageSizeChange: (pageSize: number) => void
  /**
   * Total number of items
   */
  totalItems: number
  /**
   * Show page size selector
   * @default true
   */
  showPageSizeSelector?: boolean
  /**
   * Position of page size selector
   * @default 'left'
   */
  pageSizeSelectorPosition?: 'left' | 'right'
  /**
   * Show item count info
   * @default true
   */
  showItemCount?: boolean
  /**
   * Custom item count formatter
   */
  formatItemCount?: (start: number, end: number, total: number) => string
}

/**
 * Enhanced Pagination component with page size selector
 *
 * Features:
 * - Page navigation (first, prev, next, last)
 * - Page number buttons with ellipsis
 * - Page size selector (10, 25, 50, 100)
 * - Item count display
 */
export const EnhancedPagination: React.FC<EnhancedPaginationProps> = ({
  page,
  totalPages,
  onPageChange,
  pageSize,
  pageSizeOptions = [10, 25, 50, 100],
  onPageSizeChange,
  totalItems,
  showPageSizeSelector = true,
  pageSizeSelectorPosition = 'left',
  showItemCount = true,
  formatItemCount,
  siblingCount,
  showFirstLast,
  showPrevNext,
  className,
}) => {
  const startItem = totalItems === 0 ? 0 : (page - 1) * pageSize + 1
  const endItem = Math.min(page * pageSize, totalItems)

  const itemCountText =
    formatItemCount?.(startItem, endItem, totalItems) ||
    `Showing ${startItem}-${endItem} of ${totalItems} items`

  return (
    <div
      className={cn('enhanced-pagination', className)}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: spacing[4],
        padding: spacing[4],
        borderTop: `1px solid ${colors.semantic.borderDivider}`,
        background: colors.semantic.backgroundDefault,
      }}
    >
      <Stack
        direction="row"
        spacing={4}
        style={{
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        {showPageSizeSelector && pageSizeSelectorPosition === 'left' && (
          <PageSizeSelector
            pageSize={pageSize}
            pageSizeOptions={pageSizeOptions}
            onPageSizeChange={onPageSizeChange}
          />
        )}

        {showItemCount && (
          <div
            style={{
              fontSize: '14px',
              color: colors.semantic.textSecondary,
              whiteSpace: 'nowrap',
            }}
          >
            {itemCountText}
          </div>
        )}
      </Stack>

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        siblingCount={siblingCount}
        showFirstLast={showFirstLast}
        showPrevNext={showPrevNext}
      />

      {showPageSizeSelector && pageSizeSelectorPosition === 'right' && (
        <PageSizeSelector
          pageSize={pageSize}
          pageSizeOptions={pageSizeOptions}
          onPageSizeChange={onPageSizeChange}
        />
      )}
    </div>
  )
}

EnhancedPagination.displayName = 'EnhancedPagination'

