/**
 * RetryButton Component
 *
 * Retry button component with:
 * - Max retries enforcement
 * - Disabled state when max retries reached
 * - Retry count display
 * - Loading state
 */

import React from 'react'
import { Button, ButtonProps, CircularProgress, Box } from '@mui/material'
import { Refresh as RefreshIcon } from '@mui/icons-material'

export interface RetryButtonProps extends Omit<ButtonProps, 'onClick'> {
  /**
   * Callback when retry is clicked
   */
  onRetry: () => void | Promise<void>
  /**
   * Current retry count
   * @default 0
   */
  retryCount?: number
  /**
   * Maximum retry attempts
   * @default Infinity (no limit)
   */
  maxRetries?: number
  /**
   * Whether retry is in progress
   * @default false
   */
  isRetrying?: boolean
  /**
   * Button label
   * @default 'Retry'
   */
  label?: string
}

/**
 * RetryButton component
 */
export const RetryButton: React.FC<RetryButtonProps> = ({
  onRetry,
  retryCount = 0,
  maxRetries = Infinity,
  isRetrying = false,
  label = 'Retry',
  variant = 'contained',
  disabled,
  ...buttonProps
}) => {
  const hasReachedMaxRetries = retryCount >= maxRetries
  const isDisabled = disabled || hasReachedMaxRetries || isRetrying

  const handleClick = () => {
    if (!isDisabled) {
      onRetry()
    }
  }

  const getButtonText = () => {
    if (isRetrying) {
      return 'Retrying...'
    }
    if (maxRetries !== Infinity && retryCount > 0) {
      return `${label} (${retryCount}/${maxRetries})`
    }
    return label
  }

  return (
    <Button
      variant={variant}
      startIcon={isRetrying ? <CircularProgress size={16} /> : <RefreshIcon />}
      onClick={handleClick}
      disabled={isDisabled}
      {...buttonProps}
    >
      {getButtonText()}
    </Button>
  )
}

RetryButton.displayName = 'RetryButton'

