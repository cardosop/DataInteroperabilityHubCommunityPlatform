import React from 'react'
import { cn } from '@/components/utils'
import { breakpoints } from '@/styles/tokens'

export interface GridItemProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Number of columns to span (default for all breakpoints)
   */
  span?: number
  /**
   * Responsive span values per breakpoint
   */
  xs?: number
  sm?: number
  md?: number
  lg?: number
  xl?: number
  children: React.ReactNode
}

/**
 * GridItem component for grid layout items
 */
export const GridItem = React.forwardRef<HTMLDivElement, GridItemProps>(
  ({ span, xs, sm, md, lg, xl, className, children, style, ...props }, ref) => {
    // Use the first defined value as base, or span
    const baseSpan = xs ?? sm ?? md ?? lg ?? xl ?? span

    // Build responsive styles object
    const responsiveStyles: React.CSSProperties = {
      gridColumn: baseSpan ? `span ${baseSpan} / span ${baseSpan}` : undefined,
    }

    // Add media query styles via data attributes and CSS
    // For a production app, consider using a CSS-in-JS solution
    // For now, we'll use inline styles with a style element
    const styleId = React.useId()
    const styleRules: string[] = []

    if (baseSpan) {
      styleRules.push(`.grid-item-${styleId} { grid-column: span ${baseSpan} / span ${baseSpan}; }`)
    }

    if (sm !== undefined) {
      styleRules.push(`@media (min-width: ${breakpoints.sm}px) { .grid-item-${styleId} { grid-column: span ${sm} / span ${sm}; } }`)
    }
    if (md !== undefined) {
      styleRules.push(`@media (min-width: ${breakpoints.md}px) { .grid-item-${styleId} { grid-column: span ${md} / span ${md}; } }`)
    }
    if (lg !== undefined) {
      styleRules.push(`@media (min-width: ${breakpoints.lg}px) { .grid-item-${styleId} { grid-column: span ${lg} / span ${lg}; } }`)
    }
    if (xl !== undefined) {
      styleRules.push(`@media (min-width: ${breakpoints.xl}px) { .grid-item-${styleId} { grid-column: span ${xl} / span ${xl}; } }`)
    }

    return (
      <>
        {styleRules.length > 0 && (
          <style dangerouslySetInnerHTML={{ __html: styleRules.join('\n') }} />
        )}
        <div
          ref={ref}
          className={cn(`grid-item-${styleId}`, className)}
          style={{ ...responsiveStyles, ...style }}
          {...props}
        >
          {children}
        </div>
      </>
    )
  }
)

GridItem.displayName = 'GridItem'

