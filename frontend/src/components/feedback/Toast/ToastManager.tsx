/**
 * ToastManager Component
 *
 * Enhanced toast notification system with stacking, positioning, and auto-dismiss.
 */

import React from 'react'
import { Box, Snackbar, Alert } from '@mui/material'
import { spacing } from '@/styles/tokens'
import { useToastManager, type Toast } from './useToastManager'

export interface ToastManagerProps {
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
 * ToastManager component for managing toast notifications
 */
export const ToastManager: React.FC<ToastManagerProps> = ({
  position = 'top-right',
  maxToasts = 5,
  spacing: toastSpacing = 8,
}) => {
  const { toasts, removeToast } = useToastManager({ maxToasts })

  const getPositionStyles = () => {
    const baseStyles: React.CSSProperties = {
      position: 'fixed',
      zIndex: 10000,
      display: 'flex',
      flexDirection: 'column',
      gap: `${toastSpacing}px`,
      pointerEvents: 'none',
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

  if (toasts.length === 0) return null

  return (
    <Box sx={getPositionStyles()}>
      {toasts.map((toast, index) => (
        <Snackbar
          key={toast.id}
          open={true}
          autoHideDuration={toast.duration || null}
          onClose={() => removeToast(toast.id)}
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
            margin: 0,
            marginBottom: index < toasts.length - 1 ? `${toastSpacing}px` : 0,
          }}
        >
          <Alert
            severity={toast.severity || 'info'}
            onClose={() => removeToast(toast.id)}
            action={toast.action}
            sx={{ minWidth: '300px', maxWidth: '500px' }}
          >
            {toast.message}
          </Alert>
        </Snackbar>
      ))}
    </Box>
  )
}

