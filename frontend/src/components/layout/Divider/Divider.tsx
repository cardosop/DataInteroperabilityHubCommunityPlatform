import React from 'react'
import { cn } from '@/components/utils'
import { spacing, colors } from '@/styles/tokens'

export interface DividerProps extends React.HTMLAttributes<HTMLHRElement> {
  /**
   * Orientation of the divider
   * @default 'horizontal'
   */
  orientation?: 'horizontal' | 'vertical'
  /**
   * Spacing around the divider (in spacing units)
   * @default 2
   */
  spacing?: number
  /**
   * Optional text to display in the divider
   */
  text?: string
}

/**
 * Divider component for visual separation
 */
export const Divider = React.forwardRef<HTMLHRElement, DividerProps>(
  ({ orientation = 'horizontal', spacing: spacingValue = 2, text, className, ...props }, ref) => {
    const margin = spacing[spacingValue] || spacing[2]

    if (orientation === 'vertical') {
      return (
        <hr
          ref={ref}
          className={cn('divider', 'divider-vertical', className)}
          style={{
            width: '1px',
            height: '100%',
            border: 'none',
            borderLeft: `1px solid ${colors.semantic.borderDivider}`,
            margin: `0 ${margin}px`,
            ...props.style,
          }}
          role="separator"
          aria-orientation="vertical"
          {...props}
        />
      )
    }

    if (text) {
      return (
        <div
          className={cn('divider', 'divider-with-text', className)}
          style={{
            display: 'flex',
            alignItems: 'center',
            margin: `${margin}px 0`,
            ...props.style,
          }}
        >
          <hr
            ref={ref}
            style={{
              flex: 1,
              border: 'none',
              borderTop: `1px solid ${colors.semantic.borderDivider}`,
              margin: 0,
            }}
            role="separator"
            aria-orientation="horizontal"
          />
          <span
            style={{
              padding: `0 ${spacing[4]}px`,
              color: colors.semantic.textSecondary,
              fontSize: '14px',
            }}
          >
            {text}
          </span>
          <hr
            style={{
              flex: 1,
              border: 'none',
              borderTop: `1px solid ${colors.semantic.borderDivider}`,
              margin: 0,
            }}
            role="separator"
            aria-orientation="horizontal"
          />
        </div>
      )
    }

    return (
      <hr
        ref={ref}
        className={cn('divider', 'divider-horizontal', className)}
        style={{
          width: '100%',
          height: '1px',
          border: 'none',
          borderTop: `1px solid ${colors.semantic.borderDivider}`,
          margin: `${margin}px 0`,
          ...props.style,
        }}
        role="separator"
        aria-orientation="horizontal"
        {...props}
      />
    )
  }
)

Divider.displayName = 'Divider'

