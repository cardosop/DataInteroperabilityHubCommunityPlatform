/**
 * Connection Status Indicator Component
 *
 * Real-time WebSocket connection status indicator.
 * Displays connection state with visual feedback and optional reconnect controls.
 * Handles connection loss gracefully with automatic reconnection.
 */

import React, { useEffect, useState } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import { useWebSocketConnection } from '@/hooks/useWebSocket'
import { WebSocketState } from '@/lib/api/websocket'
import { Badge } from '@/components/data-display/Badge'
import { CircularProgress } from '@/components/feedback/CircularProgress'
import { Tooltip } from '@/components/overlay/Tooltip'

export interface ConnectionStatusIndicatorProps {
  /**
   * Show reconnect button when disconnected
   * @default true
   */
  showReconnectButton?: boolean
  /**
   * Show tooltip with connection details
   * @default true
   */
  showTooltip?: boolean
  /**
   * Size of the indicator
   * @default 'md'
   */
  size?: 'sm' | 'md' | 'lg'
  /**
   * Custom className
   */
  className?: string
  /**
   * Callback when connection is lost
   */
  onConnectionLost?: () => void
  /**
   * Callback when connection is restored
   */
  onConnectionRestored?: () => void
}

/**
 * Connection Status Indicator component
 */
export const ConnectionStatusIndicator: React.FC<ConnectionStatusIndicatorProps> = ({
  showReconnectButton = true,
  showTooltip = true,
  size = 'md',
  className,
  onConnectionLost,
  onConnectionRestored,
}) => {
  const { status, connect, disconnect } = useWebSocketConnection()
  const [wasConnected, setWasConnected] = useState(false)
  const [connectionLostTime, setConnectionLostTime] = useState<Date | null>(null)

  // Track connection state changes for callbacks
  useEffect(() => {
    if (status.isConnected && !wasConnected && connectionLostTime) {
      // Connection restored
      setConnectionLostTime(null)
      onConnectionRestored?.()
    } else if (!status.isConnected && wasConnected && status.state !== WebSocketState.CONNECTING) {
      // Connection lost
      setConnectionLostTime(new Date())
      onConnectionLost?.()
    }
    setWasConnected(status.isConnected)
  }, [status.isConnected, status.state, wasConnected, connectionLostTime, onConnectionLost, onConnectionRestored])

  const getStatusConfig = () => {
    switch (status.state) {
      case WebSocketState.CONNECTED:
        return {
          icon: (
            <svg
              width={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
              height={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
              viewBox="0 0 24 24"
              fill="none"
              stroke={colors.success[500]}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M5 13a10 10 0 0 1 14 0M5 13a10 10 0 0 0 7 7M5 13l3-3M22 13l-3-3M16 8h.01M12 8h.01M8 8h.01" />
            </svg>
          ),
          label: 'Connected',
          color: 'success' as const,
          tooltip: 'WebSocket connection is active',
        }
      case WebSocketState.CONNECTING:
        return {
          icon: <CircularProgress size={size === 'sm' ? 'sm' : 'md'} />,
          label: 'Connecting',
          color: 'info' as const,
          tooltip: 'Establishing WebSocket connection...',
        }
      case WebSocketState.RECONNECTING:
        return {
          icon: <CircularProgress size={size === 'sm' ? 'sm' : 'md'} />,
          label: `Reconnecting${status.reconnectAttempt ? ` (${status.reconnectAttempt}/${status.maxReconnectAttempts || '?'})` : ''}`,
          color: 'warning' as const,
          tooltip: `Reconnecting...${status.reconnectAttempt ? ` Attempt ${status.reconnectAttempt} of ${status.maxReconnectAttempts || '?'}` : ''}`,
        }
      case WebSocketState.ERROR:
        return {
          icon: (
            <svg
              width={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
              height={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
              viewBox="0 0 24 24"
              fill="none"
              stroke={colors.error[500]}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          ),
          label: 'Error',
          color: 'error' as const,
          tooltip: status.error || 'WebSocket connection error',
        }
      case WebSocketState.DISCONNECTED:
      default:
        return {
          icon: (
            <svg
              width={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
              height={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
              viewBox="0 0 24 24"
              fill="none"
              stroke={colors.gray[500]}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="1" y1="1" x2="23" y2="23" />
              <path d="M16.72 11.06A10 10 0 0 1 5 13M5 13l3-3M22 13l-3-3M10.68 4.71A10 10 0 0 1 22 11" />
            </svg>
          ),
          label: 'Disconnected',
          color: 'neutral' as const,
          tooltip: 'WebSocket connection is not active',
        }
    }
  }

  const statusConfig = getStatusConfig()

  const handleReconnect = () => {
    if (status.isConnected) {
      disconnect()
    }
    connect()
  }

  const indicatorContent = (
    <div
      className={cn('connection-status-indicator', className)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing[2],
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing[1],
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: size === 'sm' ? '16px' : size === 'md' ? '18px' : '20px',
            height: size === 'sm' ? '16px' : size === 'md' ? '18px' : '20px',
          }}
        >
          {statusConfig.icon}
        </div>
        <Badge variant={statusConfig.color} size={size === 'lg' ? 'md' : 'sm'}>
          {statusConfig.label}
        </Badge>
      </div>
      {showReconnectButton && !status.isConnected && !status.isConnecting && !status.isReconnecting && (
        <button
          onClick={handleReconnect}
          disabled={status.isConnecting || status.isReconnecting}
          aria-label="Reconnect WebSocket"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: size === 'sm' ? '20px' : size === 'md' ? '24px' : '28px',
            height: size === 'sm' ? '20px' : size === 'md' ? '24px' : '28px',
            background: 'transparent',
            border: 'none',
            cursor: status.isConnecting || status.isReconnecting ? 'not-allowed' : 'pointer',
            borderRadius: borderRadius.sm,
            padding: 0,
            transition: 'background 0.2s',
            opacity: status.isConnecting || status.isReconnecting ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (!status.isConnecting && !status.isReconnecting) {
              e.currentTarget.style.background = colors.semantic.actionHover
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
          }}
          onFocus={(e) => {
            e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          <svg
            width={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
            height={size === 'sm' ? 14 : size === 'md' ? 16 : 18}
            viewBox="0 0 24 24"
            fill="none"
            stroke={colors.semantic.textPrimary}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      )}
    </div>
  )

  if (showTooltip) {
    return (
      <Tooltip content={statusConfig.tooltip} placement="bottom">
        {indicatorContent}
      </Tooltip>
    )
  }

  return indicatorContent
}

ConnectionStatusIndicator.displayName = 'ConnectionStatusIndicator'
