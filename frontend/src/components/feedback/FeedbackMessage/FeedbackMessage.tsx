/**
 * FeedbackMessage Component
 *
 * Enhanced success/error feedback component with clear messages and actions.
 */

import React from 'react'
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  IconButton,
  Collapse,
} from '@mui/material'
import {
  Close as CloseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'

export interface FeedbackMessageProps {
  /**
   * Severity of the message
   */
  severity: 'success' | 'error' | 'warning' | 'info'
  /**
   * Title of the message
   */
  title?: string
  /**
   * Main message content
   */
  message: string
  /**
   * Detailed description
   */
  description?: string
  /**
   * Whether the message is dismissible
   */
  dismissible?: boolean
  /**
   * Callback when message is dismissed
   */
  onDismiss?: () => void
  /**
   * Primary action button
   */
  action?: {
    label: string
    onClick: () => void
    variant?: 'contained' | 'outlined' | 'text'
  }
  /**
   * Secondary action button
   */
  secondaryAction?: {
    label: string
    onClick: () => void
    variant?: 'contained' | 'outlined' | 'text'
  }
  /**
   * Whether to show icon
   */
  showIcon?: boolean
  /**
   * Custom icon
   */
  icon?: React.ReactNode
  /**
   * Variant of the alert
   */
  variant?: 'standard' | 'filled' | 'outlined'
  /**
   * Whether the message is visible
   */
  visible?: boolean
}

/**
 * FeedbackMessage component for success/error feedback
 */
export const FeedbackMessage: React.FC<FeedbackMessageProps> = ({
  severity,
  title,
  message,
  description,
  dismissible = false,
  onDismiss,
  action,
  secondaryAction,
  showIcon = true,
  icon,
  variant = 'standard',
  visible = true,
}) => {
  const getIcon = () => {
    if (icon) return icon
    switch (severity) {
      case 'success':
        return <SuccessIcon />
      case 'error':
        return <ErrorIcon />
      case 'warning':
        return <WarningIcon />
      case 'info':
      default:
        return <InfoIcon />
    }
  }

  return (
    <Collapse in={visible}>
      <Alert
        severity={severity}
        variant={variant}
        icon={showIcon ? getIcon() : false}
        onClose={dismissible ? onDismiss : undefined}
        sx={{
          marginBottom: spacing[2],
          '& .MuiAlert-action': {
            alignItems: 'flex-start',
            paddingTop: spacing[1],
          },
        }}
      >
        {title && <AlertTitle>{title}</AlertTitle>}
        <Box>
          <Box sx={{ marginBottom: description || action || secondaryAction ? spacing[1] : 0 }}>
            {message}
          </Box>
          {description && (
            <Box
              sx={{
                marginTop: spacing[1],
                fontSize: '0.875rem',
                color: 'text.secondary',
              }}
            >
              {description}
            </Box>
          )}
          {(action || secondaryAction) && (
            <Box
              sx={{
                display: 'flex',
                gap: spacing[2],
                marginTop: spacing[2],
                flexWrap: 'wrap',
              }}
            >
              {action && (
                <Button
                  size="small"
                  variant={action.variant || 'contained'}
                  onClick={action.onClick}
                >
                  {action.label}
                </Button>
              )}
              {secondaryAction && (
                <Button
                  size="small"
                  variant={secondaryAction.variant || 'outlined'}
                  onClick={secondaryAction.onClick}
                >
                  {secondaryAction.label}
                </Button>
              )}
            </Box>
          )}
        </Box>
      </Alert>
    </Collapse>
  )
}

