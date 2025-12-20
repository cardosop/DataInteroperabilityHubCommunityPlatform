/**
 * NetworkErrorBanner Component
 *
 * Network status banner component that displays:
 * - Offline status
 * - Slow connection warnings
 * - Auto-dismisses when connection is restored
 */

import React from 'react'
import { Alert, AlertTitle, Box } from '@mui/material'
import { CloudOff as OfflineIcon, SignalWifiStatusbar4 as SlowConnectionIcon } from '@mui/icons-material'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'

export interface NetworkErrorBannerProps {
  /**
   * Whether to show slow connection warnings
   * @default true
   */
  showSlowConnection?: boolean
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * NetworkErrorBanner component
 */
export const NetworkErrorBanner: React.FC<NetworkErrorBannerProps> = ({
  showSlowConnection = true,
  className,
}) => {
  const { isOffline, isSlowConnection, effectiveType } = useNetworkStatus()

  // Don't render if online and not slow connection
  if (!isOffline && (!showSlowConnection || !isSlowConnection)) {
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
      ) : isSlowConnection && showSlowConnection ? (
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

NetworkErrorBanner.displayName = 'NetworkErrorBanner'

