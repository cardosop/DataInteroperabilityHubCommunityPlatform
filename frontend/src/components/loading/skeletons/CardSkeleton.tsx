import React from 'react'
import { Skeleton } from '@/components/feedback/Skeleton'
import { Card } from '@/components/data-display/Card'
import { spacing } from '@/styles/tokens'

export interface CardSkeletonProps {
  /**
   * Whether to show header skeleton
   * @default true
   */
  showHeader?: boolean
  /**
   * Whether to show image skeleton
   * @default false
   */
  showImage?: boolean
  /**
   * Number of text lines in content
   * @default 3
   */
  contentLines?: number
  /**
   * Whether to show action buttons skeleton
   * @default false
   */
  showActions?: boolean
  className?: string
}

/**
 * CardSkeleton component for card loading placeholders
 */
export const CardSkeleton: React.FC<CardSkeletonProps> = ({
  showHeader = true,
  showImage = false,
  contentLines = 3,
  showActions = false,
  className,
}) => {
  return (
    <Card className={className}>
      {showImage && (
        <div style={{ marginBottom: spacing[4] }}>
          <Skeleton variant="rectangular" width="100%" height="200px" />
        </div>
      )}
      {showHeader && (
        <div style={{ marginBottom: spacing[3] }}>
          <Skeleton variant="text" width="60%" height="24px" />
          <div style={{ marginTop: spacing[2] }}>
            <Skeleton variant="text" width="40%" height="16px" />
          </div>
        </div>
      )}
      <div style={{ marginBottom: spacing[3] }}>
        {Array.from({ length: contentLines }).map((_, index) => (
          <div
            key={index}
            style={{
              marginBottom: index < contentLines - 1 ? spacing[2] : 0,
            }}
          >
            <Skeleton
              variant="text"
              width={index === contentLines - 1 ? '80%' : '100%'}
              height="16px"
            />
          </div>
        ))}
      </div>
      {showActions && (
        <div
          style={{
            display: 'flex',
            gap: spacing[2],
            marginTop: spacing[4],
          }}
        >
          <Skeleton variant="rectangular" width="100px" height="36px" />
          <Skeleton variant="rectangular" width="80px" height="36px" />
        </div>
      )}
    </Card>
  )
}

CardSkeleton.displayName = 'CardSkeleton'

