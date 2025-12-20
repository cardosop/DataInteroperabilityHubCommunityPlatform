/**
 * Connection Status Hook
 *
 * Enhanced hook for managing WebSocket connection status with graceful
 * connection loss handling and user notifications.
 *
 * This hook wraps useWebSocketConnection and adds:
 * - Connection loss detection
 * - Automatic reconnection handling
 * - User notification callbacks
 * - Connection state tracking
 */

import { useEffect, useRef, useState } from 'react'
import { useWebSocketConnection, type ConnectionStatus } from './useWebSocket'
import { WebSocketState } from '@/lib/api/websocket'
import type { WebSocketClientOptions } from '@/lib/api/websocket'

export interface UseConnectionStatusOptions extends WebSocketClientOptions {
  /**
   * Callback when connection is lost
   */
  onConnectionLost?: () => void
  /**
   * Callback when connection is restored
   */
  onConnectionRestored?: () => void
  /**
   * Callback when reconnection attempts are exhausted
   */
  onReconnectionFailed?: () => void
  /**
   * Whether to automatically connect on mount
   * @default true
   */
  autoConnect?: boolean
}

export interface UseConnectionStatusReturn {
  /**
   * Current connection status
   */
  status: ConnectionStatus
  /**
   * Whether connection is currently active
   */
  isConnected: boolean
  /**
   * Whether connection is being established
   */
  isConnecting: boolean
  /**
   * Whether connection is reconnecting
   */
  isReconnecting: boolean
  /**
   * Whether connection is disconnected
   */
  isDisconnected: boolean
  /**
   * Manual connect function
   */
  connect: () => Promise<void>
  /**
   * Manual disconnect function
   */
  disconnect: () => void
  /**
   * Time when connection was lost (if applicable)
   */
  connectionLostTime: Date | null
  /**
   * Whether connection was previously connected
   */
  wasConnected: boolean
}

/**
 * Hook for managing connection status with graceful error handling
 *
 * @param options - Configuration options
 * @returns Connection status and management functions
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const {
 *     status,
 *     isConnected,
 *     connectionLostTime,
 *     connect,
 *   } = useConnectionStatus({
 *     onConnectionLost: () => {
 *       console.log('Connection lost!')
 *     },
 *     onConnectionRestored: () => {
 *       console.log('Connection restored!')
 *     },
 *   })
 *
 *   return (
 *     <div>
 *       {isConnected ? 'Connected' : 'Disconnected'}
 *       {connectionLostTime && (
 *         <span>Lost at: {connectionLostTime.toLocaleString()}</span>
 *       )}
 *     </div>
 *   )
 * }
 * ```
 */
export function useConnectionStatus(
  options: UseConnectionStatusOptions = {}
): UseConnectionStatusReturn {
  const {
    onConnectionLost,
    onConnectionRestored,
    onReconnectionFailed,
    autoConnect = true,
    ...websocketOptions
  } = options

  const { status, connect, disconnect, client } = useWebSocketConnection(websocketOptions)
  const [wasConnected, setWasConnected] = useState(false)
  const [connectionLostTime, setConnectionLostTime] = useState<Date | null>(null)
  const callbacksRef = useRef({ onConnectionLost, onConnectionRestored, onReconnectionFailed })
  const previousReconnectAttemptRef = useRef<number | undefined>(undefined)

  // Update callbacks ref when they change
  useEffect(() => {
    callbacksRef.current = {
      onConnectionLost,
      onConnectionRestored,
      onReconnectionFailed,
    }
  }, [onConnectionLost, onConnectionRestored, onReconnectionFailed])

  // Track connection state changes
  useEffect(() => {
    const isCurrentlyConnected = status.isConnected
    const isCurrentlyReconnecting = status.isReconnecting
    const reconnectAttempt = status.reconnectAttempt
    const maxReconnectAttempts = status.maxReconnectAttempts

    // Connection restored
    if (isCurrentlyConnected && !wasConnected && connectionLostTime) {
      setConnectionLostTime(null)
      callbacksRef.current.onConnectionRestored?.()
    }
    // Connection lost (not just connecting for the first time)
    else if (
      !isCurrentlyConnected &&
      wasConnected &&
      status.state !== WebSocketState.CONNECTING &&
      !isCurrentlyReconnecting
    ) {
      setConnectionLostTime(new Date())
      callbacksRef.current.onConnectionLost?.()
    }
    // Reconnection failed (max attempts reached)
    else if (
      isCurrentlyReconnecting &&
      reconnectAttempt !== undefined &&
      maxReconnectAttempts !== undefined &&
      reconnectAttempt >= maxReconnectAttempts &&
      previousReconnectAttemptRef.current !== undefined &&
      previousReconnectAttemptRef.current < maxReconnectAttempts
    ) {
      callbacksRef.current.onReconnectionFailed?.()
    }

    // Update previous reconnect attempt
    if (reconnectAttempt !== undefined) {
      previousReconnectAttemptRef.current = reconnectAttempt
    }

    setWasConnected(isCurrentlyConnected)
  }, [
    status.isConnected,
    status.isReconnecting,
    status.state,
    status.reconnectAttempt,
    status.maxReconnectAttempts,
    wasConnected,
    connectionLostTime,
  ])

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && !status.isConnected && !status.isConnecting && !status.isReconnecting) {
      connect().catch((error) => {
        console.error('Failed to auto-connect:', error)
      })
    }
  }, [autoConnect, status.isConnected, status.isConnecting, status.isReconnecting, connect])

  return {
    status,
    isConnected: status.isConnected,
    isConnecting: status.isConnecting,
    isReconnecting: status.isReconnecting,
    isDisconnected: status.isDisconnected,
    connect,
    disconnect,
    connectionLostTime,
    wasConnected,
  }
}

