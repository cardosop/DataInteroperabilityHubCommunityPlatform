/**
 * useOfflineQueue Hook
 *
 * React hook for managing offline action queue with:
 * - Automatic persistence to localStorage
 * - Automatic sync on reconnect
 * - Real-time updates
 * - Retry logic
 * - Partial sync failure handling
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { OfflineQueue, type QueuedAction, type SyncResult } from '@/lib/offline/OfflineQueue'
import { OfflineQueuePersistence } from '@/lib/offline/OfflineQueuePersistence'
import { useNetworkStatus } from './useNetworkStatus'
import { apiClient } from '@/lib/api/client'

export interface UseOfflineQueueOptions {
  /**
   * Whether to persist queue to localStorage
   * @default true
   */
  persist?: boolean
  /**
   * Storage key for persistence
   * @default 'offline-queue'
   */
  storageKey?: string
  /**
   * Maximum queue size
   * @default 100
   */
  maxSize?: number
  /**
   * Maximum retry attempts
   * @default 3
   */
  maxRetries?: number
  /**
   * Auto-sync on reconnect
   * @default true
   */
  autoSync?: boolean
  /**
   * Auto-save interval in milliseconds
   * @default 1000
   */
  autoSaveInterval?: number
}

/**
 * useOfflineQueue Hook
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { queue, addAction, queuedCount, isSyncing } = useOfflineQueue()
 *
 *   const handleSubmit = async () => {
 *     try {
 *       await apiClient.post('/api/v1/assets/', data)
 *     } catch (error) {
 *       if (isOffline) {
 *         addAction('POST', '/api/v1/assets/', data)
 *       }
 *     }
 *   }
 *
 *   return (
 *     <div>
 *       {queuedCount > 0 && <div>{queuedCount} actions queued</div>}
 *       <button onClick={handleSubmit}>Submit</button>
 *     </div>
 *   )
 * }
 * ```
 */
export function useOfflineQueue(options: UseOfflineQueueOptions = {}) {
  const {
    persist = true,
    storageKey = 'offline-queue',
    maxSize = 100,
    maxRetries = 3,
    autoSync = true,
    autoSaveInterval = 1000,
  } = options

  const [queuedActions, setQueuedActions] = useState<QueuedAction[]>([])
  const [isSyncing, setIsSyncing] = useState(false)
  const [syncErrors, setSyncErrors] = useState<SyncResult['errors']>([])
  const queueRef = useRef<OfflineQueue | null>(null)
  const persistenceRef = useRef<OfflineQueuePersistence | null>(null)
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const { isOnline } = useNetworkStatus()

  // Initialize queue and persistence
  useEffect(() => {
    queueRef.current = new OfflineQueue({
      maxSize,
      maxRetries,
    })

    if (persist) {
      persistenceRef.current = new OfflineQueuePersistence(storageKey)
    }

    // Load persisted actions
    if (persist && persistenceRef.current) {
      const loaded = persistenceRef.current.load()
      loaded.forEach((action) => {
        // Re-add to queue (will generate new ID if needed)
        queueRef.current?.add({
          method: action.method,
          url: action.url,
          data: action.data,
          headers: action.headers,
          config: action.config,
          priority: action.priority,
          metadata: action.metadata,
        })
      })
    }

    // Subscribe to queue changes
    const unsubscribe = queueRef.current.subscribe((updatedActions) => {
      setQueuedActions(updatedActions)

      // Auto-save with debounce
      if (persist && persistenceRef.current) {
        if (saveTimeoutRef.current) {
          clearTimeout(saveTimeoutRef.current)
        }
        saveTimeoutRef.current = setTimeout(() => {
          if (persistenceRef.current) {
            persistenceRef.current.save(updatedActions)
          }
        }, autoSaveInterval)
      }
    })

    // Initial load
    setQueuedActions(queueRef.current.getAll())

    return () => {
      unsubscribe()
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [maxSize, maxRetries, persist, storageKey, autoSaveInterval])

  // Execute action using API client
  const executeAction = useCallback(async (action: QueuedAction): Promise<any> => {
    const config: any = {
      ...action.config,
      url: action.url,
      method: action.method.toLowerCase(),
      data: action.data,
      headers: {
        ...action.headers,
      },
    }

    switch (action.method) {
      case 'GET':
        return await apiClient.get(action.url, config)
      case 'POST':
        return await apiClient.post(action.url, action.data, config)
      case 'PUT':
        return await apiClient.put(action.url, action.data, config)
      case 'PATCH':
        return await apiClient.patch(action.url, action.data, config)
      case 'DELETE':
        return await apiClient.delete(action.url, config)
      default:
        throw new Error(`Unsupported HTTP method: ${action.method}`)
    }
  }, [])

  // Sync queue when online
  const sync = useCallback(async (): Promise<SyncResult> => {
    if (!queueRef.current || !isOnline) {
      return {
        success: false,
        processed: 0,
        failed: 0,
        errors: [],
      }
    }

    setIsSyncing(true)
    setSyncErrors([])

    try {
      const result = await queueRef.current.sync(executeAction)
      setSyncErrors(result.errors)
      return result
    } finally {
      setIsSyncing(false)
    }
  }, [isOnline, executeAction])

  // Auto-sync on reconnect
  useEffect(() => {
    if (autoSync && isOnline && queuedActions.length > 0 && !isSyncing) {
      sync()
    }
  }, [isOnline, autoSync, queuedActions.length, isSyncing, sync])

  // Add action to queue
  const addAction = useCallback(
    (
      method: QueuedAction['method'],
      url: string,
      data?: any,
      options?: {
        headers?: Record<string, string>
        config?: any
        priority?: number
        metadata?: Record<string, any>
      }
    ): string => {
      if (!queueRef.current) {
        throw new Error('Offline queue not initialized')
      }

      return queueRef.current.add({
        method,
        url,
        data,
        headers: options?.headers,
        config: options?.config,
        priority: options?.priority,
        metadata: options?.metadata,
      })
    },
    []
  )

  // Remove action from queue
  const removeAction = useCallback((id: string) => {
    if (!queueRef.current) return false
    return queueRef.current.remove(id)
  }, [])

  // Clear all actions
  const clear = useCallback(() => {
    if (!queueRef.current) return

    queueRef.current.clear()

    // Clear persistence
    if (persist && persistenceRef.current) {
      persistenceRef.current.clear()
    }
  }, [persist])

  return {
    queuedActions,
    queuedCount: queuedActions.length,
    isSyncing,
    syncErrors,
    addAction,
    removeAction,
    clear,
    sync,
    get: useCallback((id: string) => queueRef.current?.get(id), []),
  }
}

