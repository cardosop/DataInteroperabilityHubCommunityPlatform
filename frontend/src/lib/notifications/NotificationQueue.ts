/**
 * Notification Queue
 *
 * Queue management for notifications with:
 * - Priority-based ordering
 * - Maximum queue size
 * - Automatic cleanup of old notifications
 * - Duplicate detection
 */

export type NotificationSeverity = 'success' | 'warning' | 'error' | 'info'

export interface NotificationAction {
  label: string
  onClick: () => void | Promise<void>
  variant?: 'primary' | 'secondary' | 'default'
}

export interface Notification {
  id: string
  title: string
  message: string
  severity?: NotificationSeverity
  timestamp: Date
  read: boolean
  action?: NotificationAction
  actions?: NotificationAction[]
  persistent?: boolean
  autoDismiss?: number // milliseconds, 0 = no auto-dismiss
  priority?: number // Higher number = higher priority
  metadata?: Record<string, any>
}

export interface NotificationQueueOptions {
  /**
   * Maximum number of notifications in queue
   * @default 100
   */
  maxSize?: number
  /**
   * Maximum age of notifications in milliseconds
   * Notifications older than this will be automatically removed
   * @default 7 days
   */
  maxAge?: number
  /**
   * Whether to allow duplicate notifications
   * @default false
   */
  allowDuplicates?: boolean
  /**
   * Time window for duplicate detection in milliseconds
   * @default 5000
   */
  duplicateWindow?: number
}

/**
 * Notification Queue Class
 *
 * Manages a queue of notifications with priority ordering,
 * size limits, and automatic cleanup.
 */
export class NotificationQueue {
  private notifications: Notification[] = []
  private options: Required<NotificationQueueOptions>
  private listeners: Set<(notifications: Notification[]) => void> = new Set()

  constructor(options: NotificationQueueOptions = {}) {
    this.options = {
      maxSize: options.maxSize ?? 100,
      maxAge: options.maxAge ?? 7 * 24 * 60 * 60 * 1000, // 7 days
      allowDuplicates: options.allowDuplicates ?? false,
      duplicateWindow: options.duplicateWindow ?? 5000,
    }
  }

  /**
   * Subscribe to queue changes
   */
  subscribe(listener: (notifications: Notification[]) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /**
   * Notify all listeners of queue changes
   */
  private notifyListeners(): void {
    const notifications = this.getAll()
    this.listeners.forEach((listener) => {
      try {
        listener(notifications)
      } catch (error) {
        console.error('Error in notification queue listener:', error)
      }
    })
  }

  /**
   * Check if notification is a duplicate
   */
  private isDuplicate(notification: Notification): boolean {
    if (this.options.allowDuplicates) {
      return false
    }

    const now = Date.now()
    const windowStart = now - this.options.duplicateWindow

    return this.notifications.some((existing) => {
      // Same title and message
      if (
        existing.title === notification.title &&
        existing.message === notification.message
      ) {
        // Within duplicate detection window
        const existingTime = existing.timestamp.getTime()
        return existingTime >= windowStart
      }
      return false
    })
  }

  /**
   * Clean up old notifications
   */
  private cleanup(): void {
    const now = Date.now()
    const maxAge = this.options.maxAge

    this.notifications = this.notifications.filter((notification) => {
      // Keep persistent notifications
      if (notification.persistent) {
        return true
      }

      const age = now - notification.timestamp.getTime()
      return age < maxAge
    })
  }

  /**
   * Add notification to queue
   */
  add(notification: Notification): boolean {
    // Check for duplicates
    if (this.isDuplicate(notification)) {
      return false
    }

    // Clean up old notifications
    this.cleanup()

    // Add notification with priority ordering
    this.notifications.push(notification)
    this.notifications.sort((a, b) => {
      // Higher priority first
      const priorityA = a.priority ?? 0
      const priorityB = b.priority ?? 0
      if (priorityA !== priorityB) {
        return priorityB - priorityA
      }
      // Newer notifications first
      return b.timestamp.getTime() - a.timestamp.getTime()
    })

    // Enforce max size
    if (this.notifications.length > this.options.maxSize) {
      // Remove oldest non-persistent notifications first
      const toRemove = this.notifications.length - this.options.maxSize
      let removed = 0
      for (let i = this.notifications.length - 1; i >= 0 && removed < toRemove; i--) {
        if (!this.notifications[i].persistent) {
          this.notifications.splice(i, 1)
          removed++
        }
      }
    }

    this.notifyListeners()
    return true
  }

  /**
   * Remove notification from queue
   */
  remove(id: string): boolean {
    const index = this.notifications.findIndex((n) => n.id === id)
    if (index !== -1) {
      this.notifications.splice(index, 1)
      this.notifyListeners()
      return true
    }
    return false
  }

  /**
   * Mark notification as read
   */
  markAsRead(id: string): boolean {
    const notification = this.notifications.find((n) => n.id === id)
    if (notification) {
      notification.read = true
      this.notifyListeners()
      return true
    }
    return false
  }

  /**
   * Mark all notifications as read
   */
  markAllAsRead(): void {
    this.notifications.forEach((notification) => {
      notification.read = true
    })
    this.notifyListeners()
  }

  /**
   * Clear all notifications
   */
  clear(): void {
    this.notifications = []
    this.notifyListeners()
  }

  /**
   * Clear read notifications
   */
  clearRead(): void {
    this.notifications = this.notifications.filter((n) => !n.read)
    this.notifyListeners()
  }

  /**
   * Get notification by ID
   */
  get(id: string): Notification | undefined {
    return this.notifications.find((n) => n.id === id)
  }

  /**
   * Get all notifications
   */
  getAll(): Notification[] {
    this.cleanup()
    return [...this.notifications]
  }

  /**
   * Get unread notifications
   */
  getUnread(): Notification[] {
    return this.notifications.filter((n) => !n.read)
  }

  /**
   * Get notifications by severity
   */
  getBySeverity(severity: NotificationSeverity): Notification[] {
    return this.notifications.filter((n) => n.severity === severity)
  }

  /**
   * Get count of unread notifications
   */
  getUnreadCount(): number {
    return this.notifications.filter((n) => !n.read).length
  }

  /**
   * Get total count
   */
  getCount(): number {
    return this.notifications.length
  }
}

