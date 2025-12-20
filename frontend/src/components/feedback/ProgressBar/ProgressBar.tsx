import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface ProgressBarProps {
  /**
   * Progress value (0-100)
   */
  value: number
  /**
   * Label for the progress bar
   */
  label?: string
  /**
   * Whether to show the value
   * @default false
   */
  showValue?: boolean
  /**
   * Variant of the progress bar
   * @default 'determinate'
   */
  variant?: 'determinate' | 'indeterminate' | 'buffer'
  /**
   * Buffer value (for buffer variant)
   */
  buffer?: number
  /**
   * Height of the progress bar
   * @default 4
   */
  height?: number
  className?: string
}

/**
 * ProgressBar component for progress indication
 */
export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  label,
  showValue = false,
  variant = 'determinate',
  buffer,
  height = 4,
  className,
}) => {
  const clampedValue = Math.min(Math.max(value, 0), 100)
  const clampedBuffer = buffer ? Math.min(Math.max(buffer, 0), 100) : undefined

  if (variant === 'indeterminate') {
    return (
      <div className={cn('progress-bar', className)}>
        {label && (
          <div
            style={{
              marginBottom: spacing[1],
              fontSize: '14px',
              color: colors.semantic.textSecondary,
            }}
          >
            {label}
          </div>
        )}
        <div
          style={{
            width: '100%',
            height: `${height}px`,
            background: colors.semantic.borderDivider,
            borderRadius: borderRadius.full,
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: '-100%',
              width: '100%',
              height: '100%',
              background: colors.primary[500],
              borderRadius: borderRadius.full,
              animation: 'progress-indeterminate 1.5s ease-in-out infinite',
            }}
          />
        </div>
        <style>
          {`
            @keyframes progress-indeterminate {
              0% {
                left: -100%;
              }
              100% {
                left: 100%;
              }
            }
          `}
        </style>
      </div>
    )
  }

  if (variant === 'buffer') {
    return (
      <div className={cn('progress-bar', className)}>
        {label && (
          <div
            style={{
              marginBottom: spacing[1],
              fontSize: '14px',
              color: colors.semantic.textSecondary,
            }}
          >
            {label}
          </div>
        )}
        <div
          style={{
            width: '100%',
            height: `${height}px`,
            background: colors.semantic.borderDivider,
            borderRadius: borderRadius.full,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: `${clampedBuffer || 0}%`,
              height: '100%',
              background: colors.semantic.borderDefault,
              borderRadius: borderRadius.full,
            }}
          />
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: `${clampedValue}%`,
              height: '100%',
              background: colors.primary[500],
              borderRadius: borderRadius.full,
              transition: 'width 0.3s ease',
            }}
          />
        </div>
        {showValue && (
          <div
            style={{
              marginTop: spacing[1],
              fontSize: '12px',
              color: colors.semantic.textSecondary,
              textAlign: 'right',
            }}
          >
            {clampedValue}%
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={cn('progress-bar', className)}>
      {label && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: spacing[1],
          }}
        >
          <span
            style={{
              fontSize: '14px',
              color: colors.semantic.textSecondary,
            }}
          >
            {label}
          </span>
          {showValue && (
            <span
              style={{
                fontSize: '14px',
                color: colors.semantic.textSecondary,
              }}
            >
              {clampedValue}%
            </span>
          )}
        </div>
      )}
      <div
        style={{
          width: '100%',
          height: `${height}px`,
          background: colors.semantic.borderDivider,
          borderRadius: borderRadius.full,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${clampedValue}%`,
            height: '100%',
            background: colors.primary[500],
            borderRadius: borderRadius.full,
            transition: 'width 0.3s ease',
          }}
        />
      </div>
    </div>
  )
}

ProgressBar.displayName = 'ProgressBar'

