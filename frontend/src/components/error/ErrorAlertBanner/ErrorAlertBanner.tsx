/**
 * ErrorAlertBanner Component
 *
 * Page-level error alert banner for displaying blocking errors.
 * Appears at the top of the page and requires user acknowledgment.
 */

import React, { useState, useCallback } from 'react'
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  IconButton,
  Collapse,
  Typography,
} from '@mui/material'
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material'
import {
  getErrorMessageConfig,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  isRecoverableError,
} from '@/utils/errorMessages'
import { ApiException, isApiException } from '@/lib/api/exceptions'
import { NetworkError, isNetworkError } from '@/lib/api/errors'

export interface ErrorAlertBannerProps {
  /**
   * Error to display
   */
  error: unknown
  /**
   * Whether the banner is dismissible
   */
  dismissible?: boolean
  /**
   * Whether the banner is collapsed by default
   */
  collapsed?: boolean
  /**
   * Show error details
   */
  showDetails?: boolean
  /**
   * Show retry button
   */
  showRetry?: boolean
  /**
   * Maximum retry attempts
   */
  maxRetries?: number
  /**
   * Current retry count
   */
  retryCount?: number
  /**
   * Callback when banner is dismissed
   */
  onDismiss?: () => void
  /**
   * Callback when retry is clicked
   */
  onRetry?: () => void
  /**
   * Custom error message
   */
  customMessage?: string
  /**
   * Custom title
   */
  customTitle?: string
  /**
   * Additional actions
   */
  actions?: React.ReactNode
}

/**
 * ErrorAlertBanner component
 */
export const ErrorAlertBanner: React.FC<ErrorAlertBannerProps> = ({
  error,
  dismissible = true,
  collapsed = false,
  showDetails = false,
  showRetry = true,
  maxRetries = 3,
  retryCount = 0,
  onDismiss,
  onRetry,
  customMessage,
  customTitle,
  actions,
}) => {
  const [isDismissed, setIsDismissed] = useState(false)
  const [isCollapsed, setIsCollapsed] = useState(collapsed)

  const errorConfig = getErrorMessageConfig(error)
  const message = customMessage || getUserFriendlyErrorMessage(error)
  const title = customTitle || getErrorTitle(error)
  const isRecoverable = isRecoverableError(error)
  const canRetry = isRecoverable && showRetry && retryCount < maxRetries

  const handleDismiss = useCallback(() => {
    setIsDismissed(true)
    if (onDismiss) {
      onDismiss()
    }
  }, [onDismiss])

  const handleRetry = useCallback(() => {
    if (onRetry && canRetry) {
      onRetry()
    }
  }, [onRetry, canRetry])

  const toggleCollapse = useCallback(() => {
    setIsCollapsed((prev) => !prev)
  }, [])

  if (isDismissed) {
    return null
  }

  return (
    <Alert
      severity={errorConfig.severity}
      sx={{
        borderRadius: 0,
        borderLeft: 'none',
        borderRight: 'none',
        borderTop: 'none',
      }}
      action={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {showDetails && (
            <IconButton
              aria-label="toggle details"
              color="inherit"
              size="small"
              onClick={toggleCollapse}
            >
              {isCollapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
            </IconButton>
          )}
          {canRetry && (
            <Button
              color="inherit"
              size="small"
              startIcon={<RefreshIcon />}
              onClick={handleRetry}
              disabled={retryCount >= maxRetries}
            >
              Retry {retryCount > 0 && `(${retryCount}/${maxRetries})`}
            </Button>
          )}
          {actions}
          {dismissible && (
            <IconButton
              aria-label="close"
              color="inherit"
              size="small"
              onClick={handleDismiss}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          )}
        </Box>
      }
    >
      <AlertTitle>{title}</AlertTitle>
      <Typography variant="body2">{message}</Typography>

      {retryCount >= maxRetries && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Maximum retry attempts reached. Please refresh the page or contact support.
        </Typography>
      )}

      <Collapse in={!isCollapsed}>
        <Box sx={{ mt: 2 }}>
          {isApiException(error) && error.requestId && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
              Request ID: {error.requestId}
            </Typography>
          )}
          {showDetails && error instanceof Error && (
            <Box
              sx={{
                mt: 1,
                p: 1,
                backgroundColor: 'action.hover',
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: '0.75rem',
                overflow: 'auto',
                maxHeight: '200px',
              }}
            >
              <Typography variant="caption" component="pre" sx={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                {error.message}
                {error.stack && (
                  <>
                    {'\n\nStack Trace:'}
                    {error.stack}
                  </>
                )}
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>
    </Alert>
  )
}

