import React from 'react'
import { Skeleton } from '@/components/feedback/Skeleton'
import { spacing, colors } from '@/styles/tokens'

export interface TableSkeletonProps {
  /**
   * Number of rows to show
   * @default 5
   */
  rows?: number
  /**
   * Number of columns to show
   * @default 4
   */
  columns?: number
  /**
   * Whether to show header row
   * @default true
   */
  showHeader?: boolean
  className?: string
}

/**
 * TableSkeleton component for table loading placeholders
 */
export const TableSkeleton: React.FC<TableSkeletonProps> = ({
  rows = 5,
  columns = 4,
  showHeader = true,
  className,
}) => {
  const columnWidths = Array.from({ length: columns }, (_, i) => {
    // Vary column widths for more realistic appearance
    const widths = ['20%', '30%', '25%', '25%']
    return widths[i % widths.length] || '25%'
  })

  return (
    <div className={className} style={{ width: '100%' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        {showHeader && (
          <thead>
            <tr style={{ borderBottom: `1px solid ${colors.semantic.borderDivider}` }}>
              {columnWidths.map((width, colIndex) => (
                <th
                  key={colIndex}
                  style={{
                    padding: spacing[3],
                    textAlign: 'left',
                  }}
                >
                  <Skeleton variant="text" width={width} height="16px" />
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr
              key={rowIndex}
              style={{
                borderBottom: `1px solid ${colors.semantic.borderDivider}`,
              }}
            >
              {columnWidths.map((width, colIndex) => (
                <td key={colIndex} style={{ padding: spacing[3] }}>
                  <Skeleton
                    variant="text"
                    width={width}
                    height={rowIndex % 2 === 0 ? '14px' : '16px'}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

TableSkeleton.displayName = 'TableSkeleton'

