import React from 'react'
import { cn } from '@/components/utils'
import { spacing } from '@/styles/tokens'

export interface SpacerProps {
  /**
   * Size of the spacer (in spacing units)
   * @default 2
   */
  size?: number
  /**
   * Whether the spacer should grow to fill available space
   * @default false
   */
  grow?: boolean
}

/**
 * Spacer component for flexible spacing
 */
export const Spacer: React.FC<SpacerProps> = ({ size = 2, grow = false }) => {
  const spacingValue = spacing[size] || spacing[2]

  return (
    <div
      className={cn('spacer')}
      style={{
        height: grow ? undefined : `${spacingValue}px`,
        width: grow ? undefined : `${spacingValue}px`,
        flexGrow: grow ? 1 : 0,
        flexShrink: 0,
      }}
      aria-hidden="true"
    />
  )
}

Spacer.displayName = 'Spacer'

