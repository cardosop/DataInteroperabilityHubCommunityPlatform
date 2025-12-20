/**
 * ErrorToast Component
 *
 * Toast notification component for displaying errors with:
 * - Auto-dismiss functionality
 * - Custom actions
 * - User-friendly error messages
 * - Configurable positioning
 */

import React from 'react'
import { Snackbar, Alert, AlertTitle, Box } from '@mui/material'
import { SnackbarOrigin } from '@mui/material/Snackbar'
import { useErrorMessage } from '@/lib/errors/useErrorMessage'

export interface ErrorToastProps {
  /**
   * Error to display
   */
  error: unknown
  /**
   * Whether the toast is open
   */
  open: boolean
  /**
   * Callback when toast is closed
   */
  onClose?: () => void
  /**
   * Auto-dismiss duration in milliseconds
   * @default 5000
   * Set to 0 to disable auto-dismiss
   */
  autoHideDuration?: number
  /**
   * Toast position
   * @default { vertical: 'top', horizontal: 'right' }
   */
  anchorOrigin?: SnackbarOrigin
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
}

/**
 * ErrorToast component
 */
export const ErrorToast: React.FC<ErrorToastProps> = ({
  error,
  open,
  onClose,
  autoHideDuration = 5000,
  anchorOrigin = { vertical: 'top', horizontal: 'right' },
  actions,
  title: customTitle,
  message: customMessage,
  className,
}) => {
  const { title: errorTitle, message: errorMessage, severity } = useErrorMessage(error)

  const finalTitle = customTitle || errorTitle
  const finalMessage = customMessage || errorMessage

  return (
    <Snackbar
      open={open}
      autoHideDuration={autoHideDuration}
      onClose={onClose}
      anchorOrigin={anchorOrigin}
      className={className}
    >
      <Alert
        severity={severity}
        onClose={onClose}
        sx={{ width: '100%' }}
        action={actions}
      >
        {finalTitle && <AlertTitle>{finalTitle}</AlertTitle>}
        {finalMessage}
      </Alert>
    </Snackbar>
  )
}

ErrorToast.displayName = 'ErrorToast'

