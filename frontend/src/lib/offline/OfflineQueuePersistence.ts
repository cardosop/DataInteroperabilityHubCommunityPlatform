/**
 * Offline Queue Persistence
 *
 * Service for persisting offline queue actions to localStorage:
 * - Save actions to localStorage
 * - Load actions from localStorage
 * - Automatic cleanup of old actions
 * - Migration support
 */

import type { QueuedAction } from './OfflineQueue'

const STORAGE_KEY = 'offline-queue'
const STORAGE_VERSION = 1

interface StoredAction {
  id: string
  method: string
  url: string
  data?: any
  headers?: Record<string, string>
  config?: any
  timestamp: string // ISO string
  retryCount: number
  lastError?: string
  priority?: number
  metadata?: Record<string, any>
}

interface StoredQueue {
  version: number
  actions: StoredAction[]
  lastSaved: string
}

/**
 * Convert QueuedAction to StoredAction
 */
function toStored(action: QueuedAction): StoredAction {
  return {
    id: action.id,
    method: action.method,
    url: action.url,
    data: action.data,
    headers: action.headers,
    config: action.config,
    timestamp: action.timestamp.toISOString(),
    retryCount: action.retryCount,
    lastError: action.lastError,
    priority: action.priority,
    metadata: action.metadata,
  }
}

/**
 * Convert StoredAction to QueuedAction
 */
function fromStored(stored: StoredAction): QueuedAction {
  return {
    id: stored.id,
    method: stored.method as QueuedAction['method'],
    url: stored.url,
    data: stored.data,
    headers: stored.headers,
    config: stored.config,
    timestamp: new Date(stored.timestamp),
    retryCount: stored.retryCount,
    lastError: stored.lastError,
    priority: stored.priority,
    metadata: stored.metadata,
  }
}

/**
 * Offline Queue Persistence Service
 */
export class OfflineQueuePersistence {
  private storageKey: string

  constructor(storageKey: string = STORAGE_KEY) {
    this.storageKey = storageKey
  }

  /**
   * Save actions to localStorage
   */
  save(actions: QueuedAction[]): boolean {
    if (typeof window === 'undefined') {
      return false
    }

    try {
      const stored: StoredQueue = {
        version: STORAGE_VERSION,
        actions: actions.map(toStored),
        lastSaved: new Date().toISOString(),
      }

      localStorage.setItem(this.storageKey, JSON.stringify(stored))
      return true
    } catch (error) {
      console.error('Failed to save offline queue to localStorage:', error)
      return false
    }
  }

  /**
   * Load actions from localStorage
   */
  load(): QueuedAction[] {
    if (typeof window === 'undefined') {
      return []
    }

    try {
      const stored = localStorage.getItem(this.storageKey)
      if (!stored) {
        return []
      }

      const parsed = JSON.parse(stored) as StoredQueue

      // Check version for migration
      if (parsed.version !== STORAGE_VERSION) {
        console.warn(
          `Offline queue storage version mismatch: expected ${STORAGE_VERSION}, got ${parsed.version}`
        )
        // Could implement migration here
      }

      return parsed.actions.map(fromStored)
    } catch (error) {
      console.error('Failed to load offline queue from localStorage:', error)
      return []
    }
  }

  /**
   * Clear all persisted actions
   */
  clear(): boolean {
    if (typeof window === 'undefined') {
      return false
    }

    try {
      localStorage.removeItem(this.storageKey)
      return true
    } catch (error) {
      console.error('Failed to clear offline queue from localStorage:', error)
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
export const offlineQueuePersistence = new OfflineQueuePersistence()

