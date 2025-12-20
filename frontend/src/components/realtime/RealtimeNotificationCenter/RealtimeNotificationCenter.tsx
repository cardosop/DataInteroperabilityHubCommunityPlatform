/**
 * Real-time Notification Center Component
 *
 * Notification center that receives notifications via WebSocket events.
 * Automatically subscribes to notification events and displays them in real-time.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { NotificationCenter, type Notification } from '@/components/feedback/NotificationCenter'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { EventMessage } from '@/lib/api/websocket'
import { useQueryClient } from '@tanstack/react-query'

export interface RealtimeNotificationCenterProps {
  /**
   * Whether the drawer is open
   */
  open: boolean
  /**
   * Callback when drawer is closed
   */
  onClose: () => void
  /**
   * Anchor position
   * @default 'right'
   */
  anchor?: 'left' | 'right' | 'top' | 'bottom'
  /**
   * Width of the drawer
   * @default 400
   */
  width?: number
  /**
   * Maximum number of notifications to keep
   * @default 100
   */
  maxNotifications?: number
  /**
   * Event types to subscribe to
   * @default All notification events
   */
  eventTypes?: string[]
  /**
   * Auto-mark notifications as read after delay (ms)
   * Set to 0 to disable
   * @default 0 (disabled)
   */
  autoMarkReadDelay?: number
}

/**
 * Map event type to notification severity
 */
const getSeverityFromEventType = (eventType: string): Notification['severity'] => {
  if (eventType.includes('.failed') || eventType.includes('.error')) {
    return 'error'
  }
  if (eventType.includes('.completed') || eventType.includes('.success')) {
    return 'success'
  }
  if (eventType.includes('.warning')) {
    return 'warning'
  }
  return 'info'
}

/**
 * Format event message for notification
 */
const formatEventMessage = (event: EventMessage): { title: string; message: string } => {
  const eventType = event.event_type
  const eventData = event.data || {}

  // Format event type as title
  const title = eventType
    .split('.')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')

  // Create message from event data
  let message = ''
  if (eventData.job_id) {
    message = `Job ${eventData.job_id.substring(0, 8)}...`
  } else if (eventData.contract_id) {
    message = `Contract ${eventData.contract_id.substring(0, 8)}...`
  } else if (eventData.asset_id) {
    message = `Asset ${eventData.asset_id.substring(0, 8)}...`
  } else if (eventData.message) {
    message = eventData.message
  } else {
    message = 'Event occurred'
  }

  // Add additional context if available
  if (eventData.error_message) {
    message += `: ${eventData.error_message}`
  } else if (eventData.status) {
    message += ` - Status: ${eventData.status}`
  }

  return { title, message }
}

/**
 * RealtimeNotificationCenter component
 */
export const RealtimeNotificationCenter: React.FC<RealtimeNotificationCenterProps> = ({
  open,
  onClose,
  anchor = 'right',
  width = 400,
  maxNotifications = 100,
  eventTypes,
  autoMarkReadDelay = 0,
}) => {
  const queryClient = useQueryClient()
  const [notifications, setNotifications] = useState<Notification[]>([])

  // Default event types to subscribe to
  const defaultEventTypes = useMemo(
    () => [
      'job.started',
      'job.completed',
      'job.failed',
      'job.cancelled',
      'contract.created',
      'contract.updated',
      'contract.validated',
      'asset.created',
      'asset.activated',
      'asset.retired',
      'dataset.created',
      'dataset.uploaded',
      'quality.check.completed',
      'quality.anomaly.detected',
      'compliance.check.completed',
      'compliance.check.failed',
    ],
    []
  )

  const subscribedEventTypes = eventTypes || defaultEventTypes

  // Handle WebSocket events
  const handleEvent = useCallback(
    (event: EventMessage) => {
      const { title, message } = formatEventMessage(event)
      const severity = getSeverityFromEventType(event.event_type)

      const notification: Notification = {
        id: event.event_id,
        title,
        message,
        severity,
        timestamp: new Date(event.timestamp),
        read: false,
        action: event.data?.job_id
          ? {
              label: 'View Job',
              onClick: () => {
                // Navigate to job detail page
                // This would typically use a router
                console.log('Navigate to job:', event.data.job_id)
              },
            }
          : undefined,
      }

      setNotifications((prev) => {
        // Add new notification at the beginning
        const updated = [notification, ...prev]

        // Limit to maxNotifications
        if (updated.length > maxNotifications) {
          return updated.slice(0, maxNotifications)
        }

        return updated
      })

      // Invalidate relevant queries based on event type
      if (event.event_type.includes('job.')) {
        queryClient.invalidateQueries({ queryKey: ['queries', 'jobs'] })
      } else if (event.event_type.includes('contract.')) {
        queryClient.invalidateQueries({ queryKey: ['queries', 'contracts'] })
      } else if (event.event_type.includes('asset.')) {
        queryClient.invalidateQueries({ queryKey: ['queries', 'assets'] })
      } else if (event.event_type.includes('dataset.')) {
        queryClient.invalidateQueries({ queryKey: ['queries', 'datasets'] })
      }
    },
    [maxNotifications, queryClient]
  )

  // Subscribe to WebSocket events
  const { isConnected } = useWebSocket(subscribedEventTypes, handleEvent)

  // Auto-mark as read
  useEffect(() => {
    if (autoMarkReadDelay > 0) {
      const timer = setTimeout(() => {
        setNotifications((prev) =>
          prev.map((n) => ({
            ...n,
            read: true,
          }))
        )
      }, autoMarkReadDelay)

      return () => clearTimeout(timer)
    }
  }, [autoMarkReadDelay, notifications])

  // Handle mark as read
  const handleMarkAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    )
  }, [])

  // Handle mark all as read
  const handleMarkAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }, [])

  // Handle dismiss
  const handleDismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  // Handle clear all
  const handleClearAll = useCallback(() => {
    setNotifications([])
  }, [])

  return (
    <NotificationCenter
      notifications={notifications}
      onMarkAsRead={handleMarkAsRead}
      onDismiss={handleDismiss}
      onMarkAllAsRead={handleMarkAllAsRead}
      onClearAll={handleClearAll}
      open={open}
      onClose={onClose}
      anchor={anchor}
      width={width}
    />
  )
}

RealtimeNotificationCenter.displayName = 'RealtimeNotificationCenter'

