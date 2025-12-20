import React from 'react'
import { cn } from '@/components/utils'
import { breakpoints, spacing } from '@/styles/tokens'

export interface ContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Maximum width of the container
   * @default 'lg'
   */
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  /**
   * Whether to apply padding
   * @default true
   */
  padding?: boolean
  children: React.ReactNode
}

const maxWidthMap = {
  sm: breakpoints.sm,
  md: breakpoints.md,
  lg: breakpoints.lg,
  xl: breakpoints.xl,
  full: '100%',
} as const

/**
 * Container component for page content with max-width and padding
 */
export const Container = React.forwardRef<HTMLDivElement, ContainerProps>(
  ({ maxWidth = 'lg', padding = true, className, children, ...props }, ref) => {
    const maxWidthValue = maxWidthMap[maxWidth]
    const maxWidthStyle =
      maxWidth === 'full' ? '100%' : `${maxWidthValue}px`

    return (
      <div
        ref={ref}
        className={cn('container', className)}
        style={{
          maxWidth: maxWidthStyle,
          margin: '0 auto',
          padding: padding
            ? `${spacing[4]}px ${spacing[6]}px`
            : undefined,
          width: '100%',
          ...props.style,
        }}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Container.displayName = 'Container'

