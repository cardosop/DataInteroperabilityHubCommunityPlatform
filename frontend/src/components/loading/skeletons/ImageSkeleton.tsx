import React from 'react'
import { Skeleton } from '@/components/feedback/Skeleton'
import { borderRadius } from '@/styles/tokens'

export interface ImageSkeletonProps {
  /**
   * Width of the image skeleton
   */
  width?: number | string
  /**
   * Height of the image skeleton
   */
  height?: number | string
  /**
   * Aspect ratio (e.g., '16/9', '4/3', '1/1')
   */
  aspectRatio?: string
  /**
   * Whether the image is circular
   * @default false
   */
  circular?: boolean
  className?: string
}

/**
 * ImageSkeleton component for image loading placeholders
 */
export const ImageSkeleton: React.FC<ImageSkeletonProps> = ({
  width,
  height,
  aspectRatio,
  circular = false,
  className,
}) => {
  const style: React.CSSProperties = {
    width: width || '100%',
    height: height,
    aspectRatio: aspectRatio,
    borderRadius: circular ? '50%' : borderRadius.md,
  }

  return (
    <div style={style} className={className}>
      <Skeleton
        variant={circular ? 'circular' : 'rectangular'}
        width={width || '100%'}
        height={height || '200px'}
      />
    </div>
  )
}

ImageSkeleton.displayName = 'ImageSkeleton'

