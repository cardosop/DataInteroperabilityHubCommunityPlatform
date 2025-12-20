/**
 * ResponsiveImage Component
 *
 * Responsive image component with srcset, sizes, and lazy loading support.
 */

import React from 'react'
import { Box, BoxProps } from '@mui/material'

export interface ResponsiveImageProps extends Omit<BoxProps, 'component'> {
  /**
   * Base image source
   */
  src: string
  /**
   * Image sources for different screen sizes
   */
  srcSet?: {
    src: string
    width: number
  }[]
  /**
   * Sizes attribute for responsive images
   */
  sizes?: string
  /**
   * Alt text for accessibility
   */
  alt: string
  /**
   * Enable lazy loading
   */
  loading?: 'lazy' | 'eager'
  /**
   * Aspect ratio (width / height)
   */
  aspectRatio?: number
  /**
   * Object fit behavior
   */
  objectFit?: 'contain' | 'cover' | 'fill' | 'none' | 'scale-down'
  /**
   * Image width
   */
  width?: number | string
  /**
   * Image height
   */
  height?: number | string
}

/**
 * ResponsiveImage component with srcset, sizes, and lazy loading
 */
export const ResponsiveImage = React.forwardRef<
  HTMLImageElement,
  ResponsiveImageProps
>(
  (
    {
      src,
      srcSet,
      sizes,
      alt,
      loading = 'lazy',
      aspectRatio,
      objectFit = 'cover',
      width,
      height,
      sx,
      ...props
    },
    ref
  ) => {
    // Build srcset string
    const srcSetString = srcSet
      ?.map((item) => `${item.src} ${item.width}w`)
      .join(', ')

    // Default sizes if not provided
    const defaultSizes =
      sizes ||
      '(max-width: 767px) 100vw, (max-width: 1023px) 50vw, 33vw'

    const imageStyle: React.CSSProperties = {
      width: width || '100%',
      height: height || aspectRatio ? 'auto' : 'auto',
      objectFit,
      display: 'block',
      ...(aspectRatio && {
        aspectRatio: `${aspectRatio}`,
      }),
    }

    return (
      <Box
        component="img"
        ref={ref}
        src={src}
        srcSet={srcSetString}
        sizes={defaultSizes}
        alt={alt}
        loading={loading}
        sx={{
          ...imageStyle,
          ...sx,
        }}
        {...props}
      />
    )
  }
)

ResponsiveImage.displayName = 'ResponsiveImage'

