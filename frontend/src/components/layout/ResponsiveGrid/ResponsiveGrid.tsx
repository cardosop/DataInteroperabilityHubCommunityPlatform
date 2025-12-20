/**
 * ResponsiveGrid Component
 *
 * Enhanced responsive grid system using MUI Grid with 12-column layout.
 * Adapts to breakpoints: mobile (1 col), tablet (2 cols), desktop (3-4 cols).
 */

import React from 'react'
import { Grid as MuiGrid, GridProps as MuiGridProps } from '@mui/material'

export interface ResponsiveGridProps extends Omit<MuiGridProps, 'container'> {
  /**
   * Grid items
   */
  children: React.ReactNode
  /**
   * Columns on mobile (xs)
   * @default 1
   */
  mobileColumns?: number
  /**
   * Columns on tablet (sm/md)
   * @default 2
   */
  tabletColumns?: number
  /**
   * Columns on desktop (lg)
   * @default 3
   */
  desktopColumns?: number
  /**
   * Columns on large desktop (xl)
   * @default 4
   */
  largeDesktopColumns?: number
}

/**
 * ResponsiveGrid component with 12-column system
 */
export const ResponsiveGrid: React.FC<ResponsiveGridProps> = ({
  children,
  mobileColumns = 1,
  tabletColumns = 2,
  desktopColumns = 3,
  largeDesktopColumns = 4,
  spacing = 2,
  ...props
}) => {
  // Calculate column span for 12-column grid
  const xsSpan = Math.floor(12 / mobileColumns)
  const smSpan = Math.floor(12 / tabletColumns)
  const mdSpan = Math.floor(12 / tabletColumns)
  const lgSpan = Math.floor(12 / desktopColumns)
  const xlSpan = Math.floor(12 / largeDesktopColumns)

  return (
    <MuiGrid container spacing={spacing} {...props}>
      {React.Children.map(children, (child) => {
        if (React.isValidElement(child)) {
          return (
            <MuiGrid
              item
              xs={xsSpan}
              sm={smSpan}
              md={mdSpan}
              lg={lgSpan}
              xl={xlSpan}
            >
              {child}
            </MuiGrid>
          )
        }
        return child
      })}
    </MuiGrid>
  )
}

