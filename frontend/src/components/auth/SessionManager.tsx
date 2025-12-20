/**
 * Session Manager Component
 *
 * High-level component that manages session timeout detection and dialog display.
 * Should be placed at the root of the application to monitor session across all pages.
 */

import React, { useState } from 'react'
import { useSessionTimeout } from '@/hooks/useSessionTimeout'
import { SessionTimeoutDialog } from './SessionTimeoutDialog'

export interface SessionManagerProps {
  /**
   * Session timeout configuration
   */
  config?: {
    /**
     * Time in seconds before expiration to show warning dialog
     * @default 120 (2 minutes)
     */
    warningThreshold?: number
    /**
     * Interval in milliseconds to check token expiration
     * @default 10000 (10 seconds)
     */
    checkInterval?: number
    /**
     * Whether to automatically refresh token when approaching expiration
     * @default true
     */
    autoRefresh?: boolean
    /**
     * Whether to automatically logout when token expires
     * @default true
     */
    autoLogout?: boolean
  }
}

/**
 * Session Manager Component
 *
 * Monitors session expiration and displays timeout dialog when needed.
 * Handles automatic token refresh and logout.
 */
export const SessionManager: React.FC<SessionManagerProps> = ({ config }) => {
  const [extending, setExtending] = useState(false)
  const { state, extendSession, logout, dismissDialog } = useSessionTimeout(config)

  const handleExtend = async () => {
    setExtending(true)
    try {
      await extendSession()
    } finally {
      setExtending(false)
    }
  }

  return (
    <>
      <SessionTimeoutDialog
        open={state.showDialog}
        timeRemaining={state.timeRemaining}
        extending={extending}
        onExtend={handleExtend}
        onLogout={logout}
        onClose={dismissDialog}
      />
    </>
  )
}

