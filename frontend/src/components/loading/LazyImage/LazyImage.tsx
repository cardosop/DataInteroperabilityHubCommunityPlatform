import React from 'react'
import { useLazyImage } from '../hooks'
import { ImageSkeleton } from '../skeletons'
import { cn } from '@/components/utils'

export interface LazyImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  /**
   * Image source URL
   */
  src: string
  /**
   * Placeholder image URL
   */
  placeholder?: string
  /**
   * Root margin for Intersection Observer
   * @default '50px'
   */
  rootMargin?: string
  /**
   * Whether to show skeleton while loading
   * @default true
   */
  showSkeleton?: boolean
  /**
   * Skeleton width
   */
  skeletonWidth?: number | string
  /**
   * Skeleton height
   */
  skeletonHeight?: number | string
  /**
   * Aspect ratio for skeleton
   */
  skeletonAspectRatio?: string
  /**
   * Whether image is circular
   */
  circular?: boolean
  /**
   * Alt text (required for accessibility)
   */
  alt: string
}

/**
 * LazyImage component for lazy loading images with Intersection Observer
 */
export const LazyImage: React.FC<LazyImageProps> = ({
  src,
  placeholder,
  rootMargin = '50px',
  showSkeleton = true,
  skeletonWidth,
  skeletonHeight,
  skeletonAspectRatio,
  circular = false,
  alt,
  className,
  style,
  ...props
}) => {
  const { imageSrc, isLoading, isLoaded, error, imgRef } = useLazyImage({
    src,
    placeholder,
    rootMargin,
  })

  if (error) {
    return (
      <div
        className={cn('lazy-image-error', className)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: skeletonWidth || '100%',
          height: skeletonHeight || '200px',
          background: '#f5f5f5',
          color: '#999',
          fontSize: '14px',
          ...style,
        }}
        role="img"
        aria-label={alt}
      >
        Failed to load image
      </div>
    )
  }

  return (
    <div
      className={cn('lazy-image-container', className)}
      style={{ position: 'relative', ...style }}
    >
      {isLoading && showSkeleton && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 1,
          }}
        >
          <ImageSkeleton
            width={skeletonWidth || '100%'}
            height={skeletonHeight}
            aspectRatio={skeletonAspectRatio}
            circular={circular}
          />
        </div>
      )}
      <img
        ref={imgRef}
        src={imageSrc}
        alt={alt}
        style={{
          width: '100%',
          height: 'auto',
          opacity: isLoaded ? 1 : 0,
          transition: 'opacity 0.3s ease',
          ...props.style,
        }}
        className={cn(props.className)}
        {...props}
      />
    </div>
  )
}

LazyImage.displayName = 'LazyImage'

