/**
 * ErrorDialog Component
 *
 * Modal dialog for displaying critical errors that require user action.
 * Blocks user interaction until the error is acknowledged or resolved.
 */

import React, { useState, useCallback } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  AlertTitle,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  IconButton,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Home as HomeIcon,
  ContactSupport as ContactSupportIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
} from '@mui/icons-material'
import {
  getErrorMessageConfig,
  getUserFriendlyErrorMessage,
  getErrorTitle,
  isRecoverableError,
} from '@/utils/errorMessages'
import { ApiException, isApiException } from '@/lib/api/exceptions'
import { NetworkError, isNetworkError } from '@/lib/api/errors'

export interface ErrorDialogProps {
  /**
   * Error to display
   */
  error: unknown
  /**
   * Whether the dialog is open
   */
  open: boolean
  /**
   * Callback when dialog is closed
   */
  onClose?: () => void
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
   * Dialog title override
   */
  dialogTitle?: string
  /**
   * Prevent closing on backdrop click
   */
  disableBackdropClick?: boolean
  /**
   * Prevent closing on escape key
   */
  disableEscapeKeyDown?: boolean
}

/**
 * ErrorDialog component
 */
export const ErrorDialog: React.FC<ErrorDialogProps> = ({
  error,
  open,
  onClose,
  showDetails = false,
  showRetry = true,
  maxRetries = 3,
  retryCount = 0,
  onRetry,
  showGoHome = false,
  onGoHome,
  showContactSupport = true,
  onContactSupport,
  customMessage,
  customTitle,
  dialogTitle,
  disableBackdropClick = false,
  disableEscapeKeyDown = false,
}) => {
  const errorConfig = getErrorMessageConfig(error)
  const message = customMessage || getUserFriendlyErrorMessage(error)
  const title = customTitle || getErrorTitle(error)
  const isRecoverable = isRecoverableError(error)
  const canRetry = isRecoverable && showRetry && retryCount < maxRetries

  const handleClose = useCallback(() => {
    if (onClose && !disableBackdropClick) {
      onClose()
    }
  }, [onClose, disableBackdropClick])

  const handleRetry = useCallback(() => {
    if (onRetry && canRetry) {
      onRetry()
    }
  }, [onRetry, canRetry])

  const handleGoHome = useCallback(() => {
    if (onGoHome) {
      onGoHome()
    } else {
      window.location.href = '/'
    }
  }, [onGoHome])

  const handleContactSupport = useCallback(() => {
    if (onContactSupport) {
      onContactSupport()
    } else {
      const errorDetails = isApiException(error)
        ? `Error ID: ${error.requestId || 'N/A'}\nStatus: ${error.status}\nCode: ${error.code}\nMessage: ${error.message}`
        : `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
      window.location.href = `mailto:support@example.com?subject=Error Report&body=${encodeURIComponent(errorDetails)}`
    }
  }, [onContactSupport, error])

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown={disableEscapeKeyDown}
      PaperProps={{
        sx: {
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">{dialogTitle || 'Error'}</Typography>
          {!disableBackdropClick && onClose && (
            <IconButton
              aria-label="close"
              onClick={handleClose}
              size="small"
              sx={{ ml: 2 }}
            >
              <CloseIcon />
            </IconButton>
          )}
        </Box>
      </DialogTitle>
      <DialogContent>
        <Alert severity={errorConfig.severity} sx={{ mb: 2 }}>
          <AlertTitle>{title}</AlertTitle>
          <Typography variant="body2">{message}</Typography>
        </Alert>

        {retryCount >= maxRetries && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Maximum retry attempts reached. Please refresh the page or contact support.
            </Typography>
          </Alert>
        )}

        {isApiException(error) && error.requestId && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
            Request ID: {error.requestId}
          </Typography>
        )}

        {showDetails && error instanceof Error && (
          <Accordion sx={{ mt: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2">Error Details</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Box
                sx={{
                  p: 1,
                  backgroundColor: 'action.hover',
                  borderRadius: 1,
                  fontFamily: 'monospace',
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '300px',
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
            </AccordionDetails>
          </Accordion>
        )}
      </DialogContent>
      <DialogActions>
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
          {!disableBackdropClick && onClose && (
            <Button onClick={handleClose} variant="text">
              Close
            </Button>
          )}
        </Stack>
      </DialogActions>
    </Dialog>
  )
}

