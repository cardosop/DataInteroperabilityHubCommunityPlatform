import React from 'react'
import { cn } from '@/components/utils'
import { LoadingSpinner } from '@/components/feedback/LoadingSpinner'
import { ProgressBar } from '@/components/feedback/ProgressBar'
import { CircularProgress } from '@/components/feedback/CircularProgress'
import { colors, spacing } from '@/styles/tokens'

export interface LoadingStateProps {
  /**
   * Loading message
   */
  message?: string
  /**
   * Progress percentage (0-100) - if provided, shows progress bar
   */
  progress?: number
  /**
   * Variant of loading indicator
   * @default 'spinner'
   */
  variant?: 'spinner' | 'progress' | 'circular'
  /**
   * Size of spinner/circular progress
   * @default 'md'
   */
  size?: 'sm' | 'md' | 'lg'
  /**
   * Whether to show percentage text
   * @default true
   */
  showPercentage?: boolean
  /**
   * Full page loading overlay
   * @default false
   */
  fullPage?: boolean
  className?: string
}

/**
 * LoadingState component with support for spinner, progress bar, and percentage
 */
export const LoadingState: React.FC<LoadingStateProps> = ({
  message,
  progress,
  variant = 'spinner',
  size = 'md',
  showPercentage = true,
  fullPage = false,
  className,
}) => {
  if (variant === 'progress' || progress !== undefined) {
    return (
      <div
        className={cn('loading-state', className)}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: spacing[3],
          padding: fullPage ? 0 : spacing[4],
          minHeight: fullPage ? '100vh' : '200px',
        }}
      >
        {message && (
          <div
            style={{
              fontSize: '16px',
              fontWeight: 500,
              color: colors.semantic.textPrimary,
              marginBottom: spacing[2],
            }}
          >
            {message}
          </div>
        )}
        <div style={{ width: '100%', maxWidth: '400px' }}>
          <ProgressBar
            value={progress ?? 0}
            showValue={showPercentage}
            variant={progress === undefined ? 'indeterminate' : 'determinate'}
          />
        </div>
        {showPercentage && progress !== undefined && (
          <div
            style={{
              fontSize: '14px',
              color: colors.semantic.textSecondary,
            }}
          >
            {Math.round(progress)}%
          </div>
        )}
      </div>
    )
  }

  if (variant === 'circular') {
    return (
      <div
        className={cn('loading-state', className)}
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: spacing[3],
          padding: fullPage ? 0 : spacing[4],
          minHeight: fullPage ? '100vh' : '200px',
        }}
      >
        <CircularProgress
          size={size}
          value={progress}
          variant={progress !== undefined ? 'determinate' : 'indeterminate'}
        />
        {message && (
          <div
            style={{
              fontSize: '14px',
              color: colors.semantic.textSecondary,
            }}
          >
            {message}
          </div>
        )}
        {showPercentage && progress !== undefined && (
          <div
            style={{
              fontSize: '14px',
              color: colors.semantic.textSecondary,
            }}
          >
            {Math.round(progress)}%
          </div>
        )}
      </div>
    )
  }

  return (
    <LoadingSpinner
      size={size}
      message={message}
      fullPage={fullPage}
      className={className}
    />
  )
}

LoadingState.displayName = 'LoadingState'

