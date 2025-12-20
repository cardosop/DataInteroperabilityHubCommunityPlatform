import React from 'react'
import { cn } from '@/components/utils'
import { spacing } from '@/styles/tokens'

export interface StackProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Direction of the stack
   * @default 'column'
   */
  direction?: 'row' | 'column'
  /**
   * Spacing between items (in spacing units)
   * @default 2
   */
  spacing?: number
  /**
   * Alignment of items along the cross axis
   */
  alignItems?: 'start' | 'center' | 'end' | 'stretch'
  /**
   * Justification of items along the main axis
   */
  justifyContent?: 'start' | 'center' | 'end' | 'space-between' | 'space-around' | 'space-evenly'
  children: React.ReactNode
}

/**
 * Stack component for vertical or horizontal layouts
 */
export const Stack = React.forwardRef<HTMLDivElement, StackProps>(
  (
    {
      direction = 'column',
      spacing: spacingValue = 2,
      alignItems,
      justifyContent,
      className,
      children,
      ...props
    },
    ref
  ) => {
    const gap = spacing[spacingValue] || spacing[2]

    return (
      <div
        ref={ref}
        className={cn('stack', className)}
        style={{
          display: 'flex',
          flexDirection: direction,
          gap: `${gap}px`,
          alignItems: alignItems === 'start' ? 'flex-start' : alignItems === 'end' ? 'flex-end' : alignItems,
          justifyContent: justifyContent === 'start' ? 'flex-start' : justifyContent === 'end' ? 'flex-end' : justifyContent,
          ...props.style,
        }}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Stack.displayName = 'Stack'

