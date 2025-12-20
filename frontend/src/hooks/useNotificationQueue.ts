/**
 * useNotificationQueue Hook
 *
 * React hook for managing notification queue with persistence:
 * - Automatic persistence to localStorage
 * - Real-time updates
 * - Queue management
 * - Auto-dismiss functionality
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { NotificationQueue, type Notification } from '@/lib/notifications/NotificationQueue'
import { NotificationPersistence } from '@/lib/notifications/NotificationPersistence'

export interface UseNotificationQueueOptions {
  /**
   * Whether to persist notifications to localStorage
   * @default true
   */
  persist?: boolean
  /**
   * Storage key for persistence
   * @default 'notifications'
   */
  storageKey?: string
  /**
   * Maximum queue size
   * @default 100
   */
  maxSize?: number
  /**
   * Maximum age of notifications in milliseconds
   * @default 7 days
   */
  maxAge?: number
  /**
   * Whether to allow duplicate notifications
   * @default false
   */
  allowDuplicates?: boolean
  /**
   * Auto-save interval in milliseconds
   * @default 1000
   */
  autoSaveInterval?: number
}

/**
 * useNotificationQueue Hook
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { notifications, add, remove, markAsRead } = useNotificationQueue()
 *
 *   const handleClick = () => {
 *     add({
 *       id: '1',
 *       title: 'Success',
 *       message: 'Operation completed',
 *       severity: 'success',
 *       timestamp: new Date(),
 *       read: false,
 *     })
 *   }
 *
 *   return (
 *     <div>
 *       <button onClick={handleClick}>Show Notification</button>
 *       {notifications.map(n => (
 *         <div key={n.id}>{n.title}</div>
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useNotificationQueue(options: UseNotificationQueueOptions = {}) {
  const {
    persist = true,
    storageKey = 'notifications',
    maxSize = 100,
    maxAge = 7 * 24 * 60 * 60 * 1000, // 7 days
    allowDuplicates = false,
    autoSaveInterval = 1000,
  } = options

  const [notifications, setNotifications] = useState<Notification[]>([])
  const queueRef = useRef<NotificationQueue | null>(null)
  const persistenceRef = useRef<NotificationPersistence | null>(null)
  const autoDismissTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map())
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Initialize queue and persistence
  useEffect(() => {
    queueRef.current = new NotificationQueue({
      maxSize,
      maxAge,
      allowDuplicates,
    })

    if (persist) {
      persistenceRef.current = new NotificationPersistence(storageKey)
    }

    // Load persisted notifications
    if (persist && persistenceRef.current) {
      const loaded = persistenceRef.current.load()
      loaded.forEach((notification) => {
        queueRef.current?.add(notification)
      })
    }

    // Subscribe to queue changes
    const unsubscribe = queueRef.current.subscribe((updatedNotifications) => {
      setNotifications(updatedNotifications)

      // Auto-save with debounce
      if (persist && persistenceRef.current) {
        if (saveTimeoutRef.current) {
          clearTimeout(saveTimeoutRef.current)
        }
        saveTimeoutRef.current = setTimeout(() => {
          if (persistenceRef.current) {
            persistenceRef.current.save(updatedNotifications)
          }
        }, autoSaveInterval)
      }
    })

    // Initial load
    setNotifications(queueRef.current.getAll())

    return () => {
      unsubscribe()
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
      // Clear auto-dismiss timers
      autoDismissTimersRef.current.forEach((timer) => clearTimeout(timer))
      autoDismissTimersRef.current.clear()
    }
  }, [maxSize, maxAge, allowDuplicates, persist, storageKey, autoSaveInterval])

  // Add notification
  const add = useCallback(
    (notification: Notification) => {
      if (!queueRef.current) return false

      const added = queueRef.current.add(notification)

      // Set up auto-dismiss if configured
      if (added && notification.autoDismiss && notification.autoDismiss > 0) {
        const timer = setTimeout(() => {
          remove(notification.id)
        }, notification.autoDismiss)

        autoDismissTimersRef.current.set(notification.id, timer)
      }

      return added
    },
    []
  )

  // Remove notification
  const remove = useCallback((id: string) => {
    if (!queueRef.current) return false

    // Clear auto-dismiss timer
    const timer = autoDismissTimersRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      autoDismissTimersRef.current.delete(id)
    }

    return queueRef.current.remove(id)
  }, [])

  // Mark as read
  const markAsRead = useCallback((id: string) => {
    if (!queueRef.current) return false
    return queueRef.current.markAsRead(id)
  }, [])

  // Mark all as read
  const markAllAsRead = useCallback(() => {
    if (!queueRef.current) return
    queueRef.current.markAllAsRead()
  }, [])

  // Clear all
  const clear = useCallback(() => {
    if (!queueRef.current) return

    // Clear all auto-dismiss timers
    autoDismissTimersRef.current.forEach((timer) => clearTimeout(timer))
    autoDismissTimersRef.current.clear()

    queueRef.current.clear()

    // Clear persistence
    if (persist && persistenceRef.current) {
      persistenceRef.current.clear()
    }
  }, [persist])

  // Clear read notifications
  const clearRead = useCallback(() => {
    if (!queueRef.current) return
    queueRef.current.clearRead()
  }, [])

  // Get unread count
  const unreadCount = notifications.filter((n) => !n.read).length

  return {
    notifications,
    unreadCount,
    add,
    remove,
    markAsRead,
    markAllAsRead,
    clear,
    clearRead,
    get: useCallback((id: string) => queueRef.current?.get(id), []),
    getUnread: useCallback(() => queueRef.current?.getUnread() ?? [], []),
    getBySeverity: useCallback(
      (severity: Notification['severity']) => queueRef.current?.getBySeverity(severity ?? 'info') ?? [],
      []
    ),
  }
}

