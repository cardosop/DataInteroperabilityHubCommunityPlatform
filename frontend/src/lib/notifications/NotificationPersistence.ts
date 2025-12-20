/**
 * Notification Persistence
 *
 * Service for persisting notifications to localStorage:
 * - Save notifications to localStorage
 * - Load notifications from localStorage
 * - Automatic cleanup of old notifications
 * - Migration support
 */

import type { Notification } from './NotificationQueue'

const STORAGE_KEY = 'notifications'
const STORAGE_VERSION = 1

interface StoredNotification {
  id: string
  title: string
  message: string
  severity?: 'success' | 'warning' | 'error' | 'info'
  timestamp: string // ISO string
  read: boolean
  action?: {
    label: string
    // Note: onClick cannot be serialized, will be restored by application
  }
  actions?: Array<{
    label: string
    variant?: 'primary' | 'secondary' | 'default'
  }>
  persistent?: boolean
  autoDismiss?: number
  priority?: number
  metadata?: Record<string, any>
}

interface StoredNotifications {
  version: number
  notifications: StoredNotification[]
  lastSaved: string
}

/**
 * Convert Notification to StoredNotification
 */
function toStored(notification: Notification): StoredNotification {
  return {
    id: notification.id,
    title: notification.title,
    message: notification.message,
    severity: notification.severity,
    timestamp: notification.timestamp.toISOString(),
    read: notification.read,
    action: notification.action
      ? {
          label: notification.action.label,
        }
      : undefined,
    actions: notification.actions?.map((action) => ({
      label: action.label,
      variant: action.variant,
    })),
    persistent: notification.persistent,
    autoDismiss: notification.autoDismiss,
    priority: notification.priority,
    metadata: notification.metadata,
  }
}

/**
 * Convert StoredNotification to Notification
 */
function fromStored(stored: StoredNotification): Notification {
  return {
    id: stored.id,
    title: stored.title,
    message: stored.message,
    severity: stored.severity,
    timestamp: new Date(stored.timestamp),
    read: stored.read,
    // Note: action.onClick will need to be restored by application
    action: stored.action
      ? {
          label: stored.action.label,
          onClick: () => {
            // Placeholder - should be restored by application
            console.warn('Notification action onClick not restored from storage')
          },
        }
      : undefined,
    actions: stored.actions?.map((action) => ({
      label: action.label,
      variant: action.variant,
      onClick: () => {
        // Placeholder - should be restored by application
        console.warn('Notification action onClick not restored from storage')
      },
    })),
    persistent: stored.persistent,
    autoDismiss: stored.autoDismiss,
    priority: stored.priority,
    metadata: stored.metadata,
  }
}

/**
 * Notification Persistence Service
 */
export class NotificationPersistence {
  private storageKey: string

  constructor(storageKey: string = STORAGE_KEY) {
    this.storageKey = storageKey
  }

  /**
   * Save notifications to localStorage
   */
  save(notifications: Notification[]): boolean {
    if (typeof window === 'undefined') {
      return false
    }

    try {
      const stored: StoredNotifications = {
        version: STORAGE_VERSION,
        notifications: notifications.map(toStored),
        lastSaved: new Date().toISOString(),
      }

      localStorage.setItem(this.storageKey, JSON.stringify(stored))
      return true
    } catch (error) {
      console.error('Failed to save notifications to localStorage:', error)
      return false
    }
  }

  /**
   * Load notifications from localStorage
   */
  load(): Notification[] {
    if (typeof window === 'undefined') {
      return []
    }

    try {
      const stored = localStorage.getItem(this.storageKey)
      if (!stored) {
        return []
      }

      const parsed = JSON.parse(stored) as StoredNotifications

      // Check version for migration
      if (parsed.version !== STORAGE_VERSION) {
        console.warn(
          `Notification storage version mismatch: expected ${STORAGE_VERSION}, got ${parsed.version}`
        )
        // Could implement migration here
      }

      return parsed.notifications.map(fromStored)
    } catch (error) {
      console.error('Failed to load notifications from localStorage:', error)
      return []
    }
  }

  /**
   * Clear all persisted notifications
   */
  clear(): boolean {
    if (typeof window === 'undefined') {
      return false
    }

    try {
      localStorage.removeItem(this.storageKey)
      return true
    } catch (error) {
      console.error('Failed to clear notifications from localStorage:', error)
      return false
    }
  }

  /**
   * Get storage size in bytes (approximate)
   */
  getStorageSize(): number {
    if (typeof window === 'undefined') {
      return 0
    }

    try {
      const stored = localStorage.getItem(this.storageKey)
      return stored ? new Blob([stored]).size : 0
    } catch {
      return 0
    }
  }
}

/**
 * Default persistence instance
 */
export const notificationPersistence = new NotificationPersistence()

