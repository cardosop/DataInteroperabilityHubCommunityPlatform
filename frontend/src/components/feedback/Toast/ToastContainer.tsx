/**
 * ToastContainer Component
 *
 * Container for managing multiple toast notifications with stacking support.
 * Handles positioning, stacking, and auto-dismiss for toast notifications.
 */

import React, { useEffect, useState } from 'react'
import { Box, Snackbar as MuiSnackbar, Alert as MuiAlert } from '@mui/material'
import { spacing } from '@/styles/tokens'

export interface Toast {
  id: string
  message: string
  severity?: 'success' | 'warning' | 'error' | 'info'
  duration?: number
  action?: React.ReactNode
  onClose?: () => void
}

export interface ToastContainerProps {
  /**
   * Position of toast container
   * @default 'top-right'
   */
  position?:
    | 'top-right'
    | 'top-left'
    | 'top-center'
    | 'bottom-right'
    | 'bottom-left'
    | 'bottom-center'
  /**
   * Maximum number of toasts to show
   * @default 5
   */
  maxToasts?: number
  /**
   * Spacing between stacked toasts
   * @default 8
   */
  spacing?: number
}

/**
 * ToastContainer for managing multiple toasts
 */
export const ToastContainer: React.FC<ToastContainerProps> = ({
  position = 'top-right',
  maxToasts = 5,
  spacing: toastSpacing = 8,
}) => {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = (toast: Omit<Toast, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random()}`
    const newToast: Toast = { ...toast, id }
    setToasts((prev) => {
      const updated = [newToast, ...prev]
      return updated.slice(0, maxToasts)
    })
    return id
  }

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }

  const getPositionStyles = () => {
    const baseStyles = {
      position: 'fixed' as const,
      zIndex: 10000,
      display: 'flex',
      flexDirection: 'column' as const,
      gap: `${toastSpacing}px`,
      pointerEvents: 'none' as const,
    }

    switch (position) {
      case 'top-right':
        return { ...baseStyles, top: spacing[4], right: spacing[4] }
      case 'top-left':
        return { ...baseStyles, top: spacing[4], left: spacing[4] }
      case 'top-center':
        return {
          ...baseStyles,
          top: spacing[4],
          left: '50%',
          transform: 'translateX(-50%)',
        }
      case 'bottom-right':
        return { ...baseStyles, bottom: spacing[4], right: spacing[4] }
      case 'bottom-left':
        return { ...baseStyles, bottom: spacing[4], left: spacing[4] }
      case 'bottom-center':
        return {
          ...baseStyles,
          bottom: spacing[4],
          left: '50%',
          transform: 'translateX(-50%)',
        }
      default:
        return { ...baseStyles, top: spacing[4], right: spacing[4] }
    }
  }

  // Expose addToast via context or ref
  React.useImperativeHandle(
    React.useRef(),
    () => ({
      addToast,
      removeToast,
    }),
    []
  )

  if (toasts.length === 0) return null

  return (
    <Box sx={getPositionStyles()}>
      {toasts.map((toast, index) => (
        <MuiSnackbar
          key={toast.id}
          open={true}
          autoHideDuration={toast.duration || 5000}
          onClose={() => {
            removeToast(toast.id)
            toast.onClose?.()
          }}
          anchorOrigin={{
            vertical: position.startsWith('top') ? 'top' : 'bottom',
            horizontal:
              position.endsWith('right')
                ? 'right'
                : position.endsWith('left')
                  ? 'left'
                  : 'center',
          }}
          sx={{
            position: 'relative',
            pointerEvents: 'auto',
            transform: 'none',
            top: 'auto',
            left: 'auto',
            right: 'auto',
            bottom: 'auto',
          }}
        >
          <MuiAlert
            severity={toast.severity || 'info'}
            onClose={() => {
              removeToast(toast.id)
              toast.onClose?.()
            }}
            action={toast.action}
            sx={{ minWidth: '300px', maxWidth: '500px' }}
          >
            {toast.message}
          </MuiAlert>
        </MuiSnackbar>
      ))}
    </Box>
  )
}

