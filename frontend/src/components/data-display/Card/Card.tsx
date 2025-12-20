import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Elevation level
   * @default 1
   */
  elevation?: 1 | 2 | 4
  /**
   * Padding size (in spacing units)
   * @default 4
   */
  padding?: number
  children: React.ReactNode
}

/**
 * Card component for content containers
 */
export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ elevation = 1, padding = 4, className, children, ...props }, ref) => {
    const elevationMap = {
      1: shadows.elevation1,
      2: shadows.elevation2,
      4: shadows.elevation4,
    }

    const { style: propsStyle, ...restProps } = props

    return (
      <div
        ref={ref}
        className={cn('card', className)}
        style={{
          background: colors.semantic.backgroundDefault,
          borderRadius: borderRadius.lg,
          padding: spacing[padding],
          boxShadow: elevationMap[elevation],
          transition: 'box-shadow 0.2s',
          ...propsStyle,
        }}
        onMouseEnter={(e) => {
          if (elevation === 1) {
            e.currentTarget.style.boxShadow = shadows.elevation2
          }
        }}
        onMouseLeave={(e) => {
          if (elevation === 1) {
            e.currentTarget.style.boxShadow = elevationMap[elevation]
          }
        }}
        {...restProps}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

