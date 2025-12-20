import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface Filter {
  id: string
  label: string
  value: any
}

export interface FilterPanelProps {
  /**
   * Active filters
   */
  activeFilters: Filter[]
  /**
   * Filter controls
   */
  children: React.ReactNode
  /**
   * Callback when filters are applied
   */
  onApply?: () => void
  /**
   * Callback when filters are reset
   */
  onReset?: () => void
  /**
   * Callback when a filter is removed
   */
  onRemoveFilter?: (filterId: string) => void
  className?: string
}

/**
 * FilterPanel component for filter controls
 */
export const FilterPanel: React.FC<FilterPanelProps> = ({
  activeFilters,
  children,
  onApply,
  onReset,
  onRemoveFilter,
  className,
}) => {
  return (
    <div
      className={cn('filter-panel', className)}
      style={{
        padding: spacing[4],
        background: colors.semantic.backgroundPaper,
        border: `1px solid ${colors.semantic.borderDivider}`,
        borderRadius: borderRadius.md,
      }}
    >
      {activeFilters.length > 0 && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: spacing[2],
            marginBottom: spacing[4],
            paddingBottom: spacing[4],
            borderBottom: `1px solid ${colors.semantic.borderDivider}`,
          }}
        >
          {activeFilters.map((filter) => (
            <span
              key={filter.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: spacing[1],
                padding: `${spacing[1]}px ${spacing[2]}px`,
                background: colors.primary[50],
                color: colors.primary[700],
                borderRadius: borderRadius.md,
                fontSize: '12px',
              }}
            >
              {filter.label}: {String(filter.value)}
              {onRemoveFilter && (
                <button
                  onClick={() => onRemoveFilter(filter.id)}
                  aria-label={`Remove ${filter.label} filter`}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    fontSize: '16px',
                    lineHeight: 1,
                    color: colors.primary[700],
                  }}
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      <div style={{ marginBottom: spacing[4] }}>{children}</div>
      {(onApply || onReset) && (
        <div
          style={{
            display: 'flex',
            gap: spacing[2],
            justifyContent: 'flex-end',
          }}
        >
          {onReset && (
            <button
              onClick={onReset}
              style={{
                padding: `${spacing[2]}px ${spacing[4]}px`,
                background: 'transparent',
                border: `1px solid ${colors.semantic.borderDefault}`,
                borderRadius: borderRadius.md,
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              Reset
            </button>
          )}
          {onApply && (
            <button
              onClick={onApply}
              style={{
                padding: `${spacing[2]}px ${spacing[4]}px`,
                background: colors.primary[500],
                border: 'none',
                borderRadius: borderRadius.md,
                color: '#FFFFFF',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 500,
              }}
            >
              Apply
            </button>
          )}
        </div>
      )}
    </div>
  )
}

FilterPanel.displayName = 'FilterPanel'

