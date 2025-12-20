/**
 * ErrorAlert Component
 *
 * Alert banner component for displaying errors with:
 * - Severity variants (error, warning, info, success)
 * - Dismissible functionality
 * - Custom actions
 * - User-friendly error messages
 */

import React, { useState, useCallback } from 'react'
import { Alert, AlertTitle, IconButton, Box } from '@mui/material'
import { Close as CloseIcon } from '@mui/icons-material'
import { useErrorMessage } from '@/lib/errors/useErrorMessage'

export type ErrorSeverity = 'error' | 'warning' | 'info' | 'success'

export interface ErrorAlertProps {
  /**
   * Error to display
   */
  error: unknown
  /**
   * Alert severity
   * @default 'error'
   */
  severity?: ErrorSeverity
  /**
   * Whether the alert is dismissible
   * @default true
   */
  dismissible?: boolean
  /**
   * Callback when alert is dismissed
   */
  onDismiss?: () => void
  /**
   * Custom actions to display
   */
  actions?: React.ReactNode
  /**
   * Custom title (overrides error title)
   */
  title?: string
  /**
   * Custom message (overrides error message)
   */
  message?: string
  /**
   * Additional CSS class name
   */
  className?: string
  /**
   * Additional CSS styles
   */
  sx?: any
}

/**
 * ErrorAlert component
 */
export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  error,
  severity,
  dismissible = true,
  onDismiss,
  actions,
  title: customTitle,
  message: customMessage,
  className,
  sx,
}) => {
  const [isDismissed, setIsDismissed] = useState(false)
  const { title: errorTitle, message: errorMessage, severity: errorSeverity } = useErrorMessage(error)

  const handleDismiss = useCallback(() => {
    setIsDismissed(true)
    if (onDismiss) {
      onDismiss()
    }
  }, [onDismiss])

  if (isDismissed) {
    return null
  }

  const finalSeverity = severity || errorSeverity || 'error'
  const finalTitle = customTitle || errorTitle
  const finalMessage = customMessage || errorMessage

  return (
    <Alert
      severity={finalSeverity}
      className={className}
      sx={sx}
      action={
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
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
      {finalTitle && <AlertTitle>{finalTitle}</AlertTitle>}
      {finalMessage}
    </Alert>
  )
}

ErrorAlert.displayName = 'ErrorAlert'

