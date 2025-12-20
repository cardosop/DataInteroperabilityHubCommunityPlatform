import React from 'react'
import { Skeleton } from '@/components/feedback/Skeleton'
import { spacing } from '@/styles/tokens'

export interface TextSkeletonProps {
  /**
   * Number of lines to show
   * @default 3
   */
  lines?: number
  /**
   * Width of each line (can be array for varying widths)
   */
  width?: number | string | (number | string)[]
  /**
   * Whether to show last line as shorter
   * @default true
   */
  lastLineShorter?: boolean
  className?: string
}

/**
 * TextSkeleton component for text loading placeholders
 */
export const TextSkeleton: React.FC<TextSkeletonProps> = ({
  lines = 3,
  width,
  lastLineShorter = true,
  className,
}) => {
  const widths = Array.isArray(width)
    ? width
    : width
      ? Array(lines).fill(width)
      : undefined

  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', gap: spacing[2] }}>
      {Array.from({ length: lines }).map((_, index) => {
        const isLast = index === lines - 1
        const lineWidth = widths
          ? widths[index] || '100%'
          : isLast && lastLineShorter
            ? '60%'
            : '100%'

        return (
          <Skeleton
            key={index}
            variant="text"
            width={lineWidth}
            height="1em"
          />
        )
      })}
    </div>
  )
}

TextSkeleton.displayName = 'TextSkeleton'

