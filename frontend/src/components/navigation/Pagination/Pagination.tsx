import React, { useMemo } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface PaginationProps {
  /**
   * Current page (1-indexed)
   */
  page: number
  /**
   * Total number of pages
   */
  totalPages: number
  /**
   * Callback when page changes
   */
  onPageChange: (page: number) => void
  /**
   * Number of page buttons to show
   * @default 5
   */
  siblingCount?: number
  /**
   * Show first/last page buttons
   * @default true
   */
  showFirstLast?: boolean
  /**
   * Show previous/next buttons
   * @default true
   */
  showPrevNext?: boolean
  className?: string
}

/**
 * Pagination component for page navigation
 */
export const Pagination: React.FC<PaginationProps> = ({
  page,
  totalPages,
  onPageChange,
  siblingCount = 1,
  showFirstLast = true,
  showPrevNext = true,
  className,
}) => {
  const pageNumbers = useMemo(() => {
    const pages: (number | 'ellipsis')[] = []
    const totalNumbers = siblingCount * 2 + 5
    const totalBlocks = totalNumbers + 2

    if (totalPages <= totalBlocks) {
      // Show all pages
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      const leftSiblingIndex = Math.max(page - siblingCount, 1)
      const rightSiblingIndex = Math.min(page + siblingCount, totalPages)

      const shouldShowLeftEllipsis = leftSiblingIndex > 2
      const shouldShowRightEllipsis = rightSiblingIndex < totalPages - 1

      if (!shouldShowLeftEllipsis && shouldShowRightEllipsis) {
        const leftItemCount = 3 + 2 * siblingCount
        const leftRange: number[] = []
        for (let i = 1; i <= leftItemCount; i++) {
          leftRange.push(i)
        }
        pages.push(...leftRange, 'ellipsis', totalPages)
      } else if (shouldShowLeftEllipsis && !shouldShowRightEllipsis) {
        const rightItemCount = 3 + 2 * siblingCount
        const rightRange: number[] = []
        for (let i = totalPages - rightItemCount + 1; i <= totalPages; i++) {
          rightRange.push(i)
        }
        pages.push(1, 'ellipsis', ...rightRange)
      } else if (shouldShowLeftEllipsis && shouldShowRightEllipsis) {
        const middleRange: number[] = []
        for (let i = leftSiblingIndex; i <= rightSiblingIndex; i++) {
          middleRange.push(i)
        }
        pages.push(1, 'ellipsis', ...middleRange, 'ellipsis', totalPages)
      }
    }

    return pages
  }, [page, totalPages, siblingCount])

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages && newPage !== page) {
      onPageChange(newPage)
    }
  }

  const buttonStyle = (isActive: boolean, isDisabled: boolean) => ({
    minWidth: '40px',
    height: '40px',
    padding: `0 ${spacing[2]}px`,
    margin: `0 ${spacing[1]}px`,
    border: `1px solid ${isActive ? colors.primary[500] : colors.semantic.borderDefault}`,
    borderRadius: '4px',
    background: isActive ? colors.primary[500] : 'transparent',
    color: isActive
      ? '#FFFFFF'
      : isDisabled
        ? colors.semantic.textDisabled
        : colors.semantic.textPrimary,
    cursor: isDisabled ? 'not-allowed' : 'pointer',
    fontSize: '14px',
    fontWeight: isActive ? 500 : 400,
    transition: 'all 0.2s',
    outline: 'none',
  })

  return (
    <nav
      className={cn('pagination', className)}
      aria-label="Pagination navigation"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[1],
      }}
    >
      {showFirstLast && (
        <button
          onClick={() => handlePageChange(1)}
          disabled={page === 1}
          aria-label="First page"
          style={buttonStyle(false, page === 1)}
          onFocus={(e) => {
            if (page !== 1) {
              e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
              e.currentTarget.style.outlineOffset = '2px'
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          ««
        </button>
      )}
      {showPrevNext && (
        <button
          onClick={() => handlePageChange(page - 1)}
          disabled={page === 1}
          aria-label="Previous page"
          style={buttonStyle(false, page === 1)}
          onFocus={(e) => {
            if (page !== 1) {
              e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
              e.currentTarget.style.outlineOffset = '2px'
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          ‹
        </button>
      )}
      {pageNumbers.map((pageNum, index) => {
        if (pageNum === 'ellipsis') {
          return (
            <span
              key={`ellipsis-${index}`}
              style={{
                padding: `0 ${spacing[2]}px`,
                color: colors.semantic.textSecondary,
              }}
              aria-hidden="true"
            >
              ...
            </span>
          )
        }
        const isActive = pageNum === page
        return (
          <button
            key={pageNum}
            onClick={() => handlePageChange(pageNum)}
            aria-label={`Page ${pageNum}`}
            aria-current={isActive ? 'page' : undefined}
            style={buttonStyle(isActive, false)}
            onFocus={(e) => {
              e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
              e.currentTarget.style.outlineOffset = '2px'
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = 'none'
            }}
          >
            {pageNum}
          </button>
        )
      })}
      {showPrevNext && (
        <button
          onClick={() => handlePageChange(page + 1)}
          disabled={page === totalPages}
          aria-label="Next page"
          style={buttonStyle(false, page === totalPages)}
          onFocus={(e) => {
            if (page !== totalPages) {
              e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
              e.currentTarget.style.outlineOffset = '2px'
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          ›
        </button>
      )}
      {showFirstLast && (
        <button
          onClick={() => handlePageChange(totalPages)}
          disabled={page === totalPages}
          aria-label="Last page"
          style={buttonStyle(false, page === totalPages)}
          onFocus={(e) => {
            if (page !== totalPages) {
              e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
              e.currentTarget.style.outlineOffset = '2px'
            }
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          »»
        </button>
      )}
    </nav>
  )
}

Pagination.displayName = 'Pagination'

