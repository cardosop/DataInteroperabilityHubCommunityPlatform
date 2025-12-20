import React from 'react'
import { cn } from '@/components/utils'
import { colors, borderRadius } from '@/styles/tokens'

export interface SkeletonProps {
  /**
   * Variant of the skeleton
   * @default 'rectangular'
   */
  variant?: 'text' | 'circular' | 'rectangular'
  /**
   * Width of the skeleton
   */
  width?: number | string
  /**
   * Height of the skeleton
   */
  height?: number | string
  /**
   * Animation variant
   * @default 'pulse'
   */
  animation?: 'pulse' | 'wave' | false
  className?: string
}

/**
 * Skeleton component for loading placeholders
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  variant = 'rectangular',
  width,
  height,
  animation = 'pulse',
  className,
}) => {
  const getBorderRadius = () => {
    if (variant === 'circular') return '50%'
    if (variant === 'text') return '4px'
    return borderRadius.md
  }

  const getHeight = () => {
    if (height) return typeof height === 'number' ? `${height}px` : height
    if (variant === 'text') return '1em'
    if (variant === 'circular') return width || '40px'
    return '20px'
  }

  const getWidth = () => {
    if (width) return typeof width === 'number' ? `${width}px` : width
    if (variant === 'circular') return height || '40px'
    return '100%'
  }

  const animationStyle =
    animation === 'pulse'
      ? {
          animation: 'skeleton-pulse 1.5s ease-in-out infinite',
        }
      : animation === 'wave'
        ? {
            background: `linear-gradient(90deg, ${colors.gray[200]} 25%, ${colors.gray[100]} 50%, ${colors.gray[200]} 75%)`,
            backgroundSize: '200% 100%',
            animation: 'skeleton-wave 1.5s ease-in-out infinite',
          }
        : {}

  return (
    <>
      <div
        className={cn('skeleton', `skeleton-${variant}`, className)}
        style={{
          width: getWidth(),
          height: getHeight(),
          background: colors.gray[200],
          borderRadius: getBorderRadius(),
          ...animationStyle,
        }}
        aria-busy="true"
        aria-live="polite"
      />
      {animation && (
        <style>
          {`
            @keyframes skeleton-pulse {
              0%, 100% {
                opacity: 1;
              }
              50% {
                opacity: 0.5;
              }
            }
            @keyframes skeleton-wave {
              0% {
                background-position: 200% 0;
              }
              100% {
                background-position: -200% 0;
              }
            }
          `}
        </style>
      )}
    </>
  )
}

Skeleton.displayName = 'Skeleton'

