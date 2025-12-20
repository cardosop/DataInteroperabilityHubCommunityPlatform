/**
 * Offline Indicator Component
 *
 * Sticky top banner that displays when the user is offline:
 * - Non-intrusive design
 * - Sticky positioning at top
 * - Auto-hides when online
 * - Shows slow connection warning
 */

import React from 'react'
import { Alert, AlertTitle, Box } from '@mui/material'
import { CloudOff as OfflineIcon, SignalWifiStatusbar4 as SlowConnectionIcon } from '@mui/icons-material'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'

export interface OfflineIndicatorProps {
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * OfflineIndicator component
 */
export const OfflineIndicator: React.FC<OfflineIndicatorProps> = ({ className }) => {
  const { isOffline, isSlowConnection, effectiveType } = useNetworkStatus()

  // Don't render if online and not slow connection
  if (!isOffline && !isSlowConnection) {
    return null
  }

  return (
    <Box
      className={className}
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 1300, // Above app bar
        width: '100%',
      }}
    >
      {isOffline ? (
        <Alert
          severity="warning"
          icon={<OfflineIcon />}
          sx={{
            borderRadius: 0,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <AlertTitle>You're Offline</AlertTitle>
          Your connection has been lost. Some features may be unavailable. Changes will be saved
          when you're back online.
        </Alert>
      ) : isSlowConnection ? (
        <Alert
          severity="info"
          icon={<SlowConnectionIcon />}
          sx={{
            borderRadius: 0,
            borderBottom: '1px solid',
            borderColor: 'divider',
          }}
        >
          <AlertTitle>Slow Connection Detected</AlertTitle>
          Your connection is slow ({effectiveType || 'unknown'}). Some features may take longer to
          load.
        </Alert>
      ) : null}
    </Box>
  )
}

OfflineIndicator.displayName = 'OfflineIndicator'

