/**
 * Enhanced Real-time Notification Center Component
 *
 * Comprehensive notification center with:
 * - Real-time WebSocket event integration
 * - Notification queue management
 * - Persistence to localStorage
 * - Multiple notification actions
 * - Auto-dismiss functionality
 * - All notification types (success, warning, error, info)
 */

import React, { useEffect, useCallback } from 'react'
import { NotificationCenter } from '@/components/feedback/NotificationCenter'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useNotificationQueue } from '@/hooks/useNotificationQueue'
import type { EventMessage } from '@/lib/api/websocket'
import { useQueryClient } from '@tanstack/react-query'
import type { Notification } from '@/lib/notifications/NotificationQueue'

export interface EnhancedRealtimeNotificationCenterProps {
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
  /**
   * Whether to persist notifications
   * @default true
   */
  persist?: boolean
  /**
   * Auto-dismiss delay in milliseconds
   * Set to 0 to disable
   * @default 0 (disabled)
   */
  autoDismiss?: number
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
 * Create notification actions from event data
 */
const createNotificationActions = (event: EventMessage): Notification['actions'] => {
  const actions: Notification['actions'] = []

  if (event.data?.job_id) {
    actions.push({
      label: 'View Job',
      onClick: () => {
        // Navigate to job detail page
        window.location.href = `/jobs/${event.data.job_id}`
      },
      variant: 'primary',
    })
  }

  if (event.data?.contract_id) {
    actions.push({
      label: 'View Contract',
      onClick: () => {
        window.location.href = `/contracts/${event.data.contract_id}`
      },
      variant: 'primary',
    })
  }

  if (event.data?.asset_id) {
    actions.push({
      label: 'View Asset',
      onClick: () => {
        window.location.href = `/assets/${event.data.asset_id}`
      },
      variant: 'primary',
    })
  }

  return actions.length > 0 ? actions : undefined
}

/**
 * Enhanced RealtimeNotificationCenter component
 */
export const EnhancedRealtimeNotificationCenter: React.FC<EnhancedRealtimeNotificationCenterProps> = ({
  open,
  onClose,
  anchor = 'right',
  width = 400,
  maxNotifications = 100,
  eventTypes,
  autoMarkReadDelay = 0,
  persist = true,
  autoDismiss = 0,
}) => {
  const queryClient = useQueryClient()

  // Use notification queue hook
  const {
    notifications,
    unreadCount,
    add,
    remove,
    markAsRead,
    markAllAsRead,
    clear,
    clearRead,
  } = useNotificationQueue({
    persist,
    maxSize: maxNotifications,
  })

  // Default event types to subscribe to
  const defaultEventTypes = [
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
  ]

  const subscribedEventTypes = eventTypes || defaultEventTypes

  // Handle WebSocket events
  const handleEvent = useCallback(
    (event: EventMessage) => {
      const { title, message } = formatEventMessage(event)
      const severity = getSeverityFromEventType(event.event_type)
      const actions = createNotificationActions(event)

      const notification: Notification = {
        id: event.event_id,
        title,
        message,
        severity,
        timestamp: new Date(event.timestamp),
        read: false,
        actions,
        autoDismiss: autoDismiss > 0 ? autoDismiss : undefined,
        priority: severity === 'error' ? 10 : severity === 'warning' ? 5 : 1,
        metadata: {
          eventType: event.event_type,
          eventData: event.data,
        },
      }

      add(notification)

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
    [add, queryClient, autoDismiss]
  )

  // Subscribe to WebSocket events
  const { isConnected } = useWebSocket(subscribedEventTypes, handleEvent)

  // Auto-mark as read
  useEffect(() => {
    if (autoMarkReadDelay > 0) {
      const timer = setTimeout(() => {
        markAllAsRead()
      }, autoMarkReadDelay)

      return () => clearTimeout(timer)
    }
  }, [autoMarkReadDelay, markAllAsRead])

  // Convert notifications to NotificationCenter format
  const notificationCenterNotifications = notifications.map((n) => ({
    id: n.id,
    title: n.title,
    message: n.message,
    severity: n.severity,
    timestamp: n.timestamp,
    read: n.read,
    action: n.actions && n.actions.length > 0 ? n.actions[0] : n.action,
  }))

  return (
    <NotificationCenter
      notifications={notificationCenterNotifications}
      onMarkAsRead={markAsRead}
      onDismiss={remove}
      onMarkAllAsRead={markAllAsRead}
      onClearAll={clear}
      open={open}
      onClose={onClose}
      anchor={anchor}
      width={width}
    />
  )
}

EnhancedRealtimeNotificationCenter.displayName = 'EnhancedRealtimeNotificationCenter'

