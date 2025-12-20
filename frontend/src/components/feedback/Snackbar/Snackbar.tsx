import React, { useEffect } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import { Alert } from '../Alert'

export interface SnackbarProps {
  /**
   * Whether the snackbar is open
   */
  open: boolean
  /**
   * Message to display
   */
  message: string
  /**
   * Severity
   * @default 'info'
   */
  severity?: 'success' | 'warning' | 'error' | 'info'
  /**
   * Position of the snackbar
   * @default 'bottom'
   */
  position?: 'top' | 'bottom'
  /**
   * Auto-hide duration in milliseconds
   */
  autoHideDuration?: number
  /**
   * Callback when snackbar closes
   */
  onClose: () => void
  /**
   * Action buttons
   */
  action?: React.ReactNode
  className?: string
}

/**
 * Snackbar component for toast notifications
 */
export const Snackbar: React.FC<SnackbarProps> = ({
  open,
  message,
  severity = 'info',
  position = 'bottom',
  autoHideDuration,
  onClose,
  action,
  className,
}) => {
  useEffect(() => {
    if (open && autoHideDuration) {
      const timer = setTimeout(() => {
        onClose()
      }, autoHideDuration)
      return () => clearTimeout(timer)
    }
  }, [open, autoHideDuration, onClose])

  if (!open) return null

  return (
    <div
      className={cn('snackbar', className)}
      style={{
        position: 'fixed',
        [position]: spacing[4],
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 10000,
        minWidth: '300px',
        maxWidth: '600px',
        animation: `snackbar-slide-${position} 0.3s ease-out`,
      }}
    >
      <div
        style={{
          background: colors.semantic.backgroundDefault,
          border: `1px solid ${colors.semantic.borderDefault}`,
          borderRadius: borderRadius.md,
          boxShadow: shadows.elevation8,
          padding: spacing[3],
          display: 'flex',
          alignItems: 'center',
          gap: spacing[3],
        }}
      >
        <Alert
          severity={severity}
          message={message}
          dismissible={false}
          actions={action}
        />
        <button
          onClick={onClose}
          aria-label="Close"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: spacing[1],
            color: colors.semantic.textSecondary,
            fontSize: '18px',
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>
      <style>
        {`
          @keyframes snackbar-slide-bottom {
            from {
              transform: translateX(-50%) translateY(100%);
              opacity: 0;
            }
            to {
              transform: translateX(-50%) translateY(0);
              opacity: 1;
            }
          }
          @keyframes snackbar-slide-top {
            from {
              transform: translateX(-50%) translateY(-100%);
              opacity: 0;
            }
            to {
              transform: translateX(-50%) translateY(0);
              opacity: 1;
            }
          }
        `}
      </style>
    </div>
  )
}

Snackbar.displayName = 'Snackbar'

