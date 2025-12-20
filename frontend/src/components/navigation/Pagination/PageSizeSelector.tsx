import React from 'react'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { cn } from '@/components/utils'

export interface PageSizeSelectorProps {
  /**
   * Current page size
   */
  pageSize: number
  /**
   * Available page size options
   * @default [10, 25, 50, 100]
   */
  pageSizeOptions?: number[]
  /**
   * Callback when page size changes
   */
  onPageSizeChange: (pageSize: number) => void
  /**
   * Label text
   * @default 'Items per page:'
   */
  label?: string
  /**
   * Show label
   * @default true
   */
  showLabel?: boolean
  className?: string
}

/**
 * Page size selector component for pagination
 */
export const PageSizeSelector: React.FC<PageSizeSelectorProps> = ({
  pageSize,
  pageSizeOptions = [10, 25, 50, 100],
  onPageSizeChange,
  label = 'Items per page:',
  showLabel = true,
  className,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newPageSize = parseInt(e.target.value, 10)
    onPageSizeChange(newPageSize)
  }

  return (
    <div
      className={cn('page-size-selector', className)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing[2],
      }}
    >
      {showLabel && (
        <label
          style={{
            fontSize: '14px',
            color: colors.semantic.textSecondary,
            whiteSpace: 'nowrap',
          }}
        >
          {label}
        </label>
      )}
      <select
        value={pageSize}
        onChange={handleChange}
        aria-label="Items per page"
        style={{
          padding: `${spacing[2]}px ${spacing[3]}px`,
          border: `1px solid ${colors.semantic.borderDefault}`,
          borderRadius: borderRadius.md,
          fontSize: '14px',
          color: colors.semantic.textPrimary,
          background: colors.semantic.backgroundDefault,
          cursor: 'pointer',
          outline: 'none',
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = colors.primary[500]
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = colors.semantic.borderDefault
        }}
      >
        {pageSizeOptions.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>
    </div>
  )
}

PageSizeSelector.displayName = 'PageSizeSelector'

