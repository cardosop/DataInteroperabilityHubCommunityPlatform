import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface ErrorStateProps {
  /**
   * Error illustration or icon
   */
  illustration?: React.ReactNode
  /**
   * Error message
   */
  message: string
  /**
   * Retry button
   */
  retryButton?: React.ReactNode
  className?: string
}

/**
 * ErrorState component for error states
 */
export const ErrorState: React.FC<ErrorStateProps> = ({
  illustration,
  message,
  retryButton,
  className,
}) => {
  return (
    <div
      className={cn('error-state', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing[8],
        textAlign: 'center',
      }}
    >
      {illustration && (
        <div
          style={{
            fontSize: '64px',
            marginBottom: spacing[4],
            color: colors.error[500],
          }}
        >
          {illustration}
        </div>
      )}
      <p
        style={{
          fontSize: '16px',
          color: colors.error[500],
          margin: 0,
          marginBottom: spacing[4],
        }}
      >
        {message}
      </p>
      {retryButton && <div>{retryButton}</div>}
    </div>
  )
}

ErrorState.displayName = 'ErrorState'

