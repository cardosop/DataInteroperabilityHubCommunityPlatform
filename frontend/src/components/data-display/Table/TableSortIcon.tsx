import React from 'react'
import { ArrowUpward, ArrowDownward, UnfoldMore } from '@mui/icons-material'
import { colors } from '@/styles/tokens'

export type SortDirection = 'asc' | 'desc' | null

export interface TableSortIconProps {
  /**
   * Current sort direction
   */
  direction: SortDirection
  /**
   * Whether the column is currently sorted
   */
  isActive: boolean
  /**
   * Size of the icon
   * @default 'small'
   */
  size?: 'small' | 'medium'
}

/**
 * Sort icon component for table headers
 * Shows ascending, descending, or unsorted state
 */
export const TableSortIcon: React.FC<TableSortIconProps> = ({
  direction,
  isActive,
  size = 'small',
}) => {
  const iconSize = size === 'small' ? 16 : 20
  const iconColor = isActive ? colors.primary[500] : colors.semantic.textSecondary

  if (direction === 'asc') {
    return (
      <ArrowUpward
        sx={{
          fontSize: iconSize,
          color: iconColor,
          transition: 'color 0.2s',
        }}
        aria-label="Sorted ascending"
      />
    )
  }

  if (direction === 'desc') {
    return (
      <ArrowDownward
        sx={{
          fontSize: iconSize,
          color: iconColor,
          transition: 'color 0.2s',
        }}
        aria-label="Sorted descending"
      />
    )
  }

  return (
    <UnfoldMore
      sx={{
        fontSize: iconSize,
        color: iconColor,
        opacity: 0.5,
        transition: 'opacity 0.2s, color 0.2s',
      }}
      aria-label="Not sorted"
    />
  )
}

TableSortIcon.displayName = 'TableSortIcon'

