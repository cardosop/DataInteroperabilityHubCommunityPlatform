import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'

export interface AlertProps {
  /**
   * Severity of the alert
   * @default 'info'
   */
  severity?: 'success' | 'warning' | 'error' | 'info'
  /**
   * Title of the alert
   */
  title?: string
  /**
   * Message content
   */
  message: string
  /**
   * Whether the alert is dismissible
   * @default false
   */
  dismissible?: boolean
  /**
   * Callback when alert is dismissed
   */
  onClose?: () => void
  /**
   * Action buttons
   */
  actions?: React.ReactNode
  className?: string
}

const severityColors = {
  success: {
    bg: colors.success[50],
    border: colors.success[500],
    text: colors.success[700],
    icon: '✓',
  },
  warning: {
    bg: colors.warning[50],
    border: colors.warning[500],
    text: colors.warning[700],
    icon: '⚠',
  },
  error: {
    bg: colors.error[50],
    border: colors.error[500],
    text: colors.error[700],
    icon: '✕',
  },
  info: {
    bg: colors.info[50],
    border: colors.info[500],
    text: colors.info[700],
    icon: 'ℹ',
  },
} as const

/**
 * Alert component for alert messages
 */
export const Alert: React.FC<AlertProps> = ({
  severity = 'info',
  title,
  message,
  dismissible = false,
  onClose,
  actions,
  className,
}) => {
  const severityStyle = severityColors[severity]

  return (
    <div
      className={cn('alert', `alert-${severity}`, className)}
      role="alert"
      style={{
        padding: spacing[4],
        background: severityStyle.bg,
        borderLeft: `4px solid ${severityStyle.border}`,
        borderRadius: borderRadius.md,
        display: 'flex',
        gap: spacing[3],
        alignItems: 'flex-start',
      }}
    >
      <div style={{ fontSize: '20px', color: severityStyle.border }}>{severityStyle.icon}</div>
      <div style={{ flex: 1 }}>
        {title && (
          <div
            style={{
              fontSize: '16px',
              fontWeight: 500,
              color: severityStyle.text,
              marginBottom: spacing[1],
            }}
          >
            {title}
          </div>
        )}
        <div style={{ fontSize: '14px', color: severityStyle.text }}>{message}</div>
        {actions && (
          <div
            style={{
              marginTop: spacing[2],
              display: 'flex',
              gap: spacing[2],
            }}
          >
            {actions}
          </div>
        )}
      </div>
      {dismissible && (
        <button
          onClick={onClose}
          aria-label="Dismiss alert"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: spacing[1],
            color: severityStyle.text,
            fontSize: '18px',
            lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
    </div>
  )
}

Alert.displayName = 'Alert'

