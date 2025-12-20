import React from 'react'
import { cn } from '@/components/utils'
import { spacing } from '@/styles/tokens'

export interface GridProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Number of columns in the grid
   * @default 12
   */
  columns?: number
  /**
   * Spacing between grid items (in spacing units)
   * @default 2
   */
  spacing?: number
  children: React.ReactNode
}

/**
 * Grid component for responsive grid layouts
 */
export const Grid = React.forwardRef<HTMLDivElement, GridProps>(
  ({ columns = 12, spacing: spacingValue = 2, className, children, ...props }, ref) => {
    const gap = spacing[spacingValue] || spacing[2]

    return (
      <div
        ref={ref}
        className={cn('grid', className)}
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap: `${gap}px`,
          ...props.style,
        }}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Grid.displayName = 'Grid'

