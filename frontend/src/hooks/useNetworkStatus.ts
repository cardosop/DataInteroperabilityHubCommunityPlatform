/**
 * useNetworkStatus Hook
 *
 * React hook for detecting network status:
 * - Online/offline detection
 * - Network quality (effective type, downlink, RTT)
 * - Save data mode
 * - Real-time updates
 */

import { useState, useEffect, useCallback } from 'react'

export type EffectiveConnectionType = '2g' | '3g' | '4g' | 'slow-2g' | undefined

export interface NetworkStatus {
  /**
   * Whether the device is online
   */
  isOnline: boolean
  /**
   * Whether the device is offline
   */
  isOffline: boolean
  /**
   * Effective connection type (2g, 3g, 4g, slow-2g)
   */
  effectiveType?: EffectiveConnectionType
  /**
   * Downlink speed in Mbps
   */
  downlink?: number
  /**
   * Round-trip time in milliseconds
   */
  rtt?: number
  /**
   * Whether save data mode is enabled
   */
  saveData?: boolean
  /**
   * Whether connection is slow (2g or slow-2g)
   */
  isSlowConnection: boolean
}

/**
 * Get NetworkInformation if available
 */
function getNetworkInformation(): NetworkInformation | null {
  if (typeof navigator === 'undefined') {
    return null
  }

  // Check for NetworkInformation API
  const connection =
    (navigator as any).connection ||
    (navigator as any).mozConnection ||
    (navigator as any).webkitConnection

  return connection || null
}

/**
 * Get initial network status
 */
function getInitialNetworkStatus(): NetworkStatus {
  const isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true
  const networkInfo = getNetworkInformation()

  const effectiveType = networkInfo?.effectiveType as EffectiveConnectionType | undefined
  const downlink = networkInfo?.downlink
  const rtt = networkInfo?.rtt
  const saveData = networkInfo?.saveData

  const isSlowConnection =
    effectiveType === '2g' || effectiveType === 'slow-2g' || (downlink !== undefined && downlink < 1)

  return {
    isOnline,
    isOffline: !isOnline,
    effectiveType,
    downlink,
    rtt,
    saveData,
    isSlowConnection,
  }
}

/**
 * useNetworkStatus Hook
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { isOnline, isOffline, isSlowConnection } = useNetworkStatus()
 *
 *   if (isOffline) {
 *     return <div>You're offline</div>
 *   }
 *
 *   if (isSlowConnection) {
 *     return <div>Slow connection detected</div>
 *   }
 *
 *   return <div>Online</div>
 * }
 * ```
 */
export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>(getInitialNetworkStatus)

  const updateStatus = useCallback(() => {
    setStatus(getInitialNetworkStatus())
  }, [])

  // Listen to online/offline events
  useEffect(() => {
    const handleOnline = () => {
      updateStatus()
    }

    const handleOffline = () => {
      updateStatus()
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [updateStatus])

  // Listen to network information changes
  useEffect(() => {
    const networkInfo = getNetworkInformation()
    if (!networkInfo) {
      return
    }

    const handleChange = () => {
      updateStatus()
    }

    // NetworkInformation API events
    networkInfo.addEventListener('change', handleChange)

    return () => {
      networkInfo.removeEventListener('change', handleChange)
    }
  }, [updateStatus])

  return status
}

