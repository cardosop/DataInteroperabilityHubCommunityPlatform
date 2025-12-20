/**
 * useSessionTimeout Hook
 *
 * Monitors session expiration and provides callbacks for timeout events.
 * Automatically detects when access token is about to expire and triggers
 * appropriate actions (show dialog, extend session, or logout).
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getTokenExpiresAt,
  isTokenExpired,
  getRefreshToken,
  clearAuthTokens,
  clearCurrentUser,
} from '@/lib/api/auth'
import { refreshAuthToken } from '@/lib/api/auth'

/**
 * Session timeout configuration
 */
export interface SessionTimeoutConfig {
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

/**
 * Session timeout state
 */
export interface SessionTimeoutState {
  /**
   * Whether session is expired
   */
  isExpired: boolean
  /**
   * Whether session is about to expire (within warning threshold)
   */
  isExpiringSoon: boolean
  /**
   * Time remaining in seconds until expiration
   */
  timeRemaining: number | null
  /**
   * Whether session timeout dialog should be shown
   */
  showDialog: boolean
}

/**
 * Session timeout hook return value
 */
export interface UseSessionTimeoutReturn {
  /**
   * Current session timeout state
   */
  state: SessionTimeoutState
  /**
   * Manually trigger session extension (refresh token)
   */
  extendSession: () => Promise<boolean>
  /**
   * Manually trigger logout
   */
  logout: () => void
  /**
   * Dismiss the timeout dialog (temporary, will show again if still expiring)
   */
  dismissDialog: () => void
}

/**
 * Hook for monitoring and managing session timeout
 *
 * @param config - Session timeout configuration
 * @returns Session timeout state and control functions
 */
export function useSessionTimeout(
  config: SessionTimeoutConfig = {}
): UseSessionTimeoutReturn {
  const navigate = useNavigate()
  const {
    warningThreshold = 120, // 2 minutes
    checkInterval = 10000, // 10 seconds
    autoRefresh = true,
    autoLogout = true,
  } = config

  const [state, setState] = useState<SessionTimeoutState>({
    isExpired: false,
    isExpiringSoon: false,
    timeRemaining: null,
    showDialog: false,
  })

  const intervalRef = useRef<NodeJS.Timeout | null>(null)
  const dialogDismissedRef = useRef(false)

  /**
   * Calculate time remaining until token expiration
   */
  const calculateTimeRemaining = useCallback((): number | null => {
    const expiresAt = getTokenExpiresAt()
    if (!expiresAt) return null

    const now = Date.now()
    const remaining = Math.max(0, Math.floor((expiresAt - now) / 1000))
    return remaining
  }, [])

  /**
   * Extend session by refreshing token
   */
  const extendSession = useCallback(async (): Promise<boolean> => {
    try {
      const newToken = await refreshAuthToken({ force: false })
      if (newToken) {
        // Session extended successfully
        dialogDismissedRef.current = false
        return true
      }
      return false
    } catch (error) {
      console.error('Failed to extend session:', error)
      return false
    }
  }, [])

  /**
   * Handle logout
   */
  const handleLogout = useCallback(() => {
    clearAuthTokens()
    clearCurrentUser()
    navigate('/auth/login', { replace: true })
  }, [navigate])

  /**
   * Check session status and update state
   */
  const checkSession = useCallback(() => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) {
      // No refresh token means not authenticated
      setState({
        isExpired: true,
        isExpiringSoon: false,
        timeRemaining: null,
        showDialog: false,
      })
      return
    }

    const timeRemaining = calculateTimeRemaining()
    const isExpired = isTokenExpired(0) // Check if already expired
    const isExpiringSoon = timeRemaining !== null && timeRemaining <= warningThreshold && timeRemaining > 0

    setState((prev) => ({
      isExpired,
      isExpiringSoon,
      timeRemaining,
      showDialog: isExpiringSoon && !dialogDismissedRef.current,
    }))

    // Auto-refresh if approaching expiration
    if (autoRefresh && isExpiringSoon && !isExpired && timeRemaining !== null && timeRemaining > 30) {
      // Only auto-refresh if more than 30 seconds remaining to avoid race conditions
      extendSession().catch(() => {
        // Silent fail - will be handled by next check
      })
    }

    // Auto-logout if expired
    if (autoLogout && isExpired) {
      handleLogout()
    }
  }, [warningThreshold, autoRefresh, autoLogout, calculateTimeRemaining, extendSession, handleLogout])


  /**
   * Dismiss timeout dialog
   */
  const dismissDialog = useCallback(() => {
    dialogDismissedRef.current = true
    setState((prev) => ({ ...prev, showDialog: false }))
  }, [])

  /**
   * Set up interval to check session status
   */
  useEffect(() => {
    // Initial check
    checkSession()

    // Set up interval
    intervalRef.current = setInterval(() => {
      checkSession()
    }, checkInterval)

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [checkSession, checkInterval])

  /**
   * Recheck session after extending
   */
  const extendSessionWithRecheck = useCallback(async (): Promise<boolean> => {
    const result = await extendSession()
    if (result) {
      // Recheck session status after successful extension
      setTimeout(() => {
        checkSession()
      }, 1000)
    }
    return result
  }, [extendSession, checkSession])

  /**
   * Reset dialog dismissed flag when session is no longer expiring soon
   */
  useEffect(() => {
    if (!state.isExpiringSoon) {
      dialogDismissedRef.current = false
    }
  }, [state.isExpiringSoon])

  return {
    state,
    extendSession: extendSessionWithRecheck,
    logout: handleLogout,
    dismissDialog,
  }
}

