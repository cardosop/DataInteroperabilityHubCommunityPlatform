/**
 * ErrorDisplay Component
 *
 * Component for displaying user-friendly error messages with actions.
 */

import React from 'react'
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Typography,
  Stack,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Home as HomeIcon,
  ContactSupport as SupportIcon,
} from '@mui/icons-material'
import { useLocation } from 'react-router-dom'
import { spacing } from '@/styles/tokens'
import {
  getErrorMessageConfig,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  isRecoverableError,
} from '@/utils/errorMessages'
import { ApiError, isApiError } from '@/lib/api/errors'
import { ErrorReportButton } from '../ErrorReportButton'

export interface ErrorDisplayProps {
  /**
   * Error to display
   */
  error: unknown
  /**
   * Show error title
   */
  showTitle?: boolean
  /**
   * Show error details
   */
  showDetails?: boolean
  /**
   * Show retry button
   */
  showRetry?: boolean
  /**
   * Show go home button
   */
  showGoHome?: boolean
  /**
   * Show contact support button
   */
  showSupport?: boolean
  /**
   * Retry callback
   */
  onRetry?: () => void
  /**
   * Go home callback
   */
  onGoHome?: () => void
  /**
   * Contact support callback
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
 * ErrorDisplay component
 */
export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  showTitle = true,
  showDetails = false,
  showRetry = true,
  showGoHome = false,
  showSupport = false,
  onRetry,
  onGoHome,
  onContactSupport,
  customMessage,
  customTitle,
  fullWidth = false,
}) => {
  const location = useLocation()
  const errorConfig = getErrorMessageConfig(error)
  const message = customMessage || getUserFriendlyErrorMessage(error)
  const title = customTitle || getErrorTitle(error)
  const isRecoverable = isRecoverableError(error)
  const canRetry = isRecoverable && showRetry

  const handleRetry = () => {
    if (onRetry) {
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
      const errorDetails = isApiError(error)
        ? `Error ID: ${error.requestId || 'N/A'}\nStatus: ${error.status}\nCode: ${error.code}`
        : `Error: ${error instanceof Error ? error.message : 'Unknown error'}`

      window.location.href = `mailto:support@example.com?subject=Error Report&body=${encodeURIComponent(errorDetails)}`
    }
  }

  return (
    <Box sx={{ width: fullWidth ? '100%' : 'auto' }}>
      <Alert severity={errorConfig.severity} sx={{ marginBottom: spacing[2] }}>
        {showTitle && <AlertTitle>{title}</AlertTitle>}
        <Typography variant="body2">{message}</Typography>

        {showDetails && error instanceof Error && (
          <Box sx={{ marginTop: spacing[2] }}>
            <Typography variant="caption" color="text.secondary" component="pre" sx={{ whiteSpace: 'pre-wrap' }}>
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

        {isApiError(error) && error.requestId && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ marginTop: spacing[1] }}>
            Request ID: {error.requestId}
          </Typography>
        )}
      </Alert>

      {(canRetry || showGoHome || showSupport || errorConfig.action) && (
        <Stack direction="row" spacing={2} flexWrap="wrap">
          {canRetry && (
            <Button
              size="small"
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={handleRetry}
            >
              {errorConfig.action === 'Retry' ? errorConfig.action : 'Retry'}
            </Button>
          )}
          {showGoHome && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<HomeIcon />}
              onClick={handleGoHome}
            >
              Go Home
            </Button>
          )}
          {showSupport && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<SupportIcon />}
              onClick={handleContactSupport}
            >
              Contact Support
            </Button>
          )}
          <ErrorReportButton
            error={error}
            location={location}
            size="sm"
            variant="outline"
            onReported={(eventId) => {
              if (eventId) {
                console.log('Error reported to Sentry:', eventId)
              }
            }}
          />
          {errorConfig.action && !canRetry && errorConfig.action !== 'Retry' && (
            <Button
              size="small"
              variant="outlined"
              onClick={() => {
                if (errorConfig.action === 'Sign In') {
                  window.location.href = '/login'
                } else if (errorConfig.action === 'Contact Support') {
                  handleContactSupport()
                } else if (errorConfig.action === 'Go Back') {
                  window.history.back()
                }
              }}
            >
              {errorConfig.action}
            </Button>
          )}
        </Stack>
      )}
    </Box>
  )
}

