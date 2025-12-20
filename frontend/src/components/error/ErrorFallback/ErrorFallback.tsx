/**
 * ErrorFallback Component
 *
 * Fallback UI component for displaying errors with recovery options.
 * Used in error boundaries and error states.
 */

import React from 'react'
import {
  Box,
  Paper,
  Typography,
  Button,
  Stack,
  Alert,
  AlertTitle,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Home as HomeIcon,
  ContactSupport as ContactSupportIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'
import {
  getErrorMessageConfig,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  isRecoverableError,
} from '@/utils/errorMessages'
import { ApiException, isApiException } from '@/lib/api/exceptions'

export interface ErrorFallbackProps {
  /**
   * Error to display
   */
  error: unknown
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
   * Callback when retry is clicked
   */
  onRetry?: () => void
  /**
   * Show go home button
   */
  showGoHome?: boolean
  /**
   * Callback when go home is clicked
   */
  onGoHome?: () => void
  /**
   * Show contact support button
   */
  showContactSupport?: boolean
  /**
   * Callback when contact support is clicked
   */
  onContactSupport?: () => void
  /**
   * Custom error message
   */
  customMessage?: string
  /**
   * Custom title
   */
  customTitle?: string
  /**
   * Full width display
   */
  fullWidth?: boolean
}

/**
 * ErrorFallback component
 */
export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  showRetry = true,
  maxRetries = 3,
  retryCount = 0,
  onRetry,
  showGoHome = true,
  onGoHome,
  showContactSupport = true,
  onContactSupport,
  customMessage,
  customTitle,
  fullWidth = false,
}) => {
  const errorConfig = getErrorMessageConfig(error)
  const message = customMessage || getUserFriendlyErrorMessage(error)
  const title = customTitle || getErrorTitle(error)
  const isRecoverable = isRecoverableError(error)
  const canRetry = isRecoverable && showRetry && retryCount < maxRetries

  const handleRetry = () => {
    if (onRetry && canRetry) {
      onRetry()
    } else {
      window.location.reload()
    }
  }

  const handleGoHome = () => {
    if (onGoHome) {
      onGoHome()
    } else {
      window.location.href = '/'
    }
  }

  const handleContactSupport = () => {
    if (onContactSupport) {
      onContactSupport()
    } else {
      const errorDetails = isApiException(error)
        ? `Error ID: ${error.requestId || 'N/A'}\nStatus: ${error.status}\nCode: ${error.code}\nMessage: ${error.message}`
        : `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
      window.location.href = `mailto:support@example.com?subject=Error Report&body=${encodeURIComponent(errorDetails)}`
    }
  }

  return (
    <Box sx={{ width: fullWidth ? '100%' : 'auto', p: spacing[3] }}>
      <Paper elevation={2} sx={{ p: spacing[3] }}>
        <Alert severity={errorConfig.severity} sx={{ mb: spacing[3] }}>
          <AlertTitle>{title}</AlertTitle>
          <Typography variant="body2">{message}</Typography>
        </Alert>

        {retryCount >= maxRetries && (
          <Alert severity="warning" sx={{ mb: spacing[2] }}>
            <Typography variant="body2">
              Maximum retry attempts reached. Please refresh the page or contact support.
            </Typography>
          </Alert>
        )}

        {isApiException(error) && error.requestId && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: spacing[2] }}>
            Request ID: {error.requestId}
          </Typography>
        )}

        <Stack direction="row" spacing={2} flexWrap="wrap">
          {canRetry && (
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={handleRetry}
              disabled={retryCount >= maxRetries}
            >
              Retry {retryCount > 0 && `(${retryCount}/${maxRetries})`}
            </Button>
          )}
          {showGoHome && (
            <Button
              variant="outlined"
              startIcon={<HomeIcon />}
              onClick={handleGoHome}
            >
              Go Home
            </Button>
          )}
          {showContactSupport && (
            <Button
              variant="outlined"
              startIcon={<ContactSupportIcon />}
              onClick={handleContactSupport}
            >
              Contact Support
            </Button>
          )}
        </Stack>
      </Paper>
    </Box>
  )
}

