/**
 * Session Timeout Dialog Component
 *
 * Dialog shown when session is about to expire, giving user options to
 * extend session or logout.
 */

import React, { useEffect, useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  LinearProgress,
} from '@mui/material'
import { Alert } from '@/components/feedback'
import { spacing } from '@/styles/tokens'

export interface SessionTimeoutDialogProps {
  /**
   * Whether dialog is open
   */
  open: boolean
  /**
   * Time remaining in seconds until expiration
   */
  timeRemaining: number | null
  /**
   * Whether session extension is in progress
   */
  extending?: boolean
  /**
   * Callback when user chooses to extend session
   */
  onExtend: () => Promise<void>
  /**
   * Callback when user chooses to logout
   */
  onLogout: () => void
  /**
   * Callback when dialog is closed
   */
  onClose?: () => void
}

/**
 * Format seconds into human-readable time string
 */
function formatTimeRemaining(seconds: number): string {
  if (seconds <= 0) return '0 seconds'

  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  if (minutes === 0) {
    return `${remainingSeconds} second${remainingSeconds !== 1 ? 's' : ''}`
  }

  if (remainingSeconds === 0) {
    return `${minutes} minute${minutes !== 1 ? 's' : ''}`
  }

  return `${minutes} minute${minutes !== 1 ? 's' : ''} ${remainingSeconds} second${remainingSeconds !== 1 ? 's' : ''}`
}

/**
 * Session Timeout Dialog Component
 */
export const SessionTimeoutDialog: React.FC<SessionTimeoutDialogProps> = ({
  open,
  timeRemaining,
  extending = false,
  onExtend,
  onLogout,
  onClose,
}) => {
  const [countdown, setCountdown] = useState(timeRemaining)

  // Update countdown every second
  useEffect(() => {
    if (!open || timeRemaining === null) return

    setCountdown(timeRemaining)

    const interval = setInterval(() => {
      setCountdown((prev) => {
        const next = prev !== null ? Math.max(0, prev - 1) : null
        if (next === 0) {
          clearInterval(interval)
        }
        return next
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [open, timeRemaining])

  const handleExtend = async () => {
    try {
      await onExtend()
      if (onClose) {
        onClose()
      }
    } catch (error) {
      console.error('Failed to extend session:', error)
    }
  }

  const handleLogout = () => {
    onLogout()
    if (onClose) {
      onClose()
    }
  }

  const progressValue = countdown !== null && timeRemaining !== null && timeRemaining > 0
    ? (countdown / timeRemaining) * 100
    : 0

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown
      aria-labelledby="session-timeout-dialog-title"
      aria-describedby="session-timeout-dialog-description"
    >
      <DialogTitle id="session-timeout-dialog-title">
        Session About to Expire
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
          <Alert
            severity="warning"
            message="Your session is about to expire. Please extend your session to continue working, or sign out."
          />

          <Box>
            <Typography variant="body1" gutterBottom>
              Time remaining: <strong>{countdown !== null ? formatTimeRemaining(countdown) : 'Unknown'}</strong>
            </Typography>
            <LinearProgress
              variant="determinate"
              value={progressValue}
              sx={{ mt: 2, height: 8, borderRadius: 1 }}
              color={countdown !== null && countdown < 30 ? 'error' : 'warning'}
            />
          </Box>

          <Typography variant="body2" color="text.secondary">
            Your session will automatically expire if no action is taken. Extending your session will refresh your authentication token.
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button
          onClick={handleLogout}
          variant="outlined"
          color="inherit"
          disabled={extending}
        >
          Sign Out
        </Button>
        <Button
          onClick={handleExtend}
          variant="contained"
          disabled={extending}
          autoFocus
        >
          {extending ? 'Extending...' : 'Extend Session'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

