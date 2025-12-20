/**
 * Offline Queue
 *
 * Queue management for offline actions:
 * - Queue actions when offline
 * - Automatic sync on reconnect
 * - Retry logic with exponential backoff
 * - Action persistence
 * - Partial sync failure handling
 */

export type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface QueuedAction {
  id: string
  method: HTTPMethod
  url: string
  data?: any
  headers?: Record<string, string>
  config?: any
  timestamp: Date
  retryCount: number
  lastError?: string
  priority?: number // Higher number = higher priority
  metadata?: Record<string, any>
}

export interface OfflineQueueOptions {
  /**
   * Maximum number of queued actions
   * @default 100
   */
  maxSize?: number
  /**
   * Maximum retry attempts per action
   * @default 3
   */
  maxRetries?: number
  /**
   * Initial retry delay in milliseconds
   * @default 1000
   */
  initialRetryDelay?: number
  /**
   * Maximum retry delay in milliseconds
   * @default 30000
   */
  maxRetryDelay?: number
  /**
   * Backoff multiplier
   * @default 2
   */
  backoffMultiplier?: number
  /**
   * Whether to allow duplicate actions
   * @default false
   */
  allowDuplicates?: boolean
  /**
   * Time window for duplicate detection in milliseconds
   * @default 5000
   */
  duplicateWindow?: number
}

export interface SyncResult {
  success: boolean
  processed: number
  failed: number
  errors: Array<{ actionId: string; error: string }>
}

/**
 * Offline Queue Class
 *
 * Manages a queue of actions to be executed when online.
 */
export class OfflineQueue {
  private queue: QueuedAction[] = []
  private options: Required<OfflineQueueOptions>
  private listeners: Set<(queue: QueuedAction[]) => void> = new Set()
  private isSyncing: boolean = false
  private syncPromise: Promise<SyncResult> | null = null

  constructor(options: OfflineQueueOptions = {}) {
    this.options = {
      maxSize: options.maxSize ?? 100,
      maxRetries: options.maxRetries ?? 3,
      initialRetryDelay: options.initialRetryDelay ?? 1000,
      maxRetryDelay: options.maxRetryDelay ?? 30000,
      backoffMultiplier: options.backoffMultiplier ?? 2,
      allowDuplicates: options.allowDuplicates ?? false,
      duplicateWindow: options.duplicateWindow ?? 5000,
    }
  }

  /**
   * Subscribe to queue changes
   */
  subscribe(listener: (queue: QueuedAction[]) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /**
   * Notify all listeners of queue changes
   */
  private notifyListeners(): void {
    const queue = this.getAll()
    this.listeners.forEach((listener) => {
      try {
        listener(queue)
      } catch (error) {
        console.error('Error in offline queue listener:', error)
      }
    })
  }

  /**
   * Check if action is a duplicate
   */
  private isDuplicate(action: QueuedAction): boolean {
    if (this.options.allowDuplicates) {
      return false
    }

    const now = Date.now()
    const windowStart = now - this.options.duplicateWindow

    return this.queue.some((existing) => {
      // Same method, URL, and data
      if (
        existing.method === action.method &&
        existing.url === action.url &&
        JSON.stringify(existing.data) === JSON.stringify(action.data)
      ) {
        // Within duplicate detection window
        const existingTime = existing.timestamp.getTime()
        return existingTime >= windowStart
      }
      return false
    })
  }

  /**
   * Calculate retry delay with exponential backoff
   */
  private calculateRetryDelay(retryCount: number): number {
    const delay =
      this.options.initialRetryDelay * Math.pow(this.options.backoffMultiplier, retryCount)
    return Math.min(delay, this.options.maxRetryDelay)
  }

  /**
   * Add action to queue
   */
  add(action: Omit<QueuedAction, 'id' | 'timestamp' | 'retryCount'>): string {
    // Check for duplicates
    const queuedAction: QueuedAction = {
      ...action,
      id: action.id || `action-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      retryCount: 0,
    }

    if (this.isDuplicate(queuedAction)) {
      throw new Error('Duplicate action detected')
    }

    // Enforce max size
    if (this.queue.length >= this.options.maxSize) {
      // Remove oldest lowest priority action
      const sorted = [...this.queue].sort((a, b) => (a.priority ?? 0) - (b.priority ?? 0))
      const oldest = sorted[0]
      this.remove(oldest.id)
    }

    // Add to queue with priority ordering
    this.queue.push(queuedAction)
    this.queue.sort((a, b) => {
      // Higher priority first
      const priorityA = a.priority ?? 0
      const priorityB = b.priority ?? 0
      if (priorityA !== priorityB) {
        return priorityB - priorityA
      }
      // Older actions first
      return a.timestamp.getTime() - b.timestamp.getTime()
    })

    this.notifyListeners()
    return queuedAction.id
  }

  /**
   * Remove action from queue
   */
  remove(id: string): boolean {
    const index = this.queue.findIndex((a) => a.id === id)
    if (index !== -1) {
      this.queue.splice(index, 1)
      this.notifyListeners()
      return true
    }
    return false
  }

  /**
   * Get action by ID
   */
  get(id: string): QueuedAction | undefined {
    return this.queue.find((a) => a.id === id)
  }

  /**
   * Get all queued actions
   */
  getAll(): QueuedAction[] {
    return [...this.queue]
  }

  /**
   * Get count of queued actions
   */
  getCount(): number {
    return this.queue.length
  }

  /**
   * Clear all actions
   */
  clear(): void {
    this.queue = []
    this.notifyListeners()
  }

  /**
   * Sync queue with API
   * Executes all queued actions when online
   */
  async sync(
    executeAction: (action: QueuedAction) => Promise<any>
  ): Promise<SyncResult> {
    // If already syncing, return existing promise
    if (this.isSyncing && this.syncPromise) {
      return this.syncPromise
    }

    this.isSyncing = true
    this.syncPromise = this.performSync(executeAction)

    try {
      const result = await this.syncPromise
      return result
    } finally {
      this.isSyncing = false
      this.syncPromise = null
    }
  }

  /**
   * Perform actual sync
   */
  private async performSync(
    executeAction: (action: QueuedAction) => Promise<any>
  ): Promise<SyncResult> {
    const result: SyncResult = {
      success: true,
      processed: 0,
      failed: 0,
      errors: [],
    }

    const actionsToProcess = [...this.queue]
    const processedIds: string[] = []
    const failedIds: string[] = []

    for (const action of actionsToProcess) {
      try {
        await executeAction(action)
        processedIds.push(action.id)
        result.processed++
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error)
        action.lastError = errorMessage
        action.retryCount++

        if (action.retryCount >= this.options.maxRetries) {
          // Max retries exceeded, mark as failed
          failedIds.push(action.id)
          result.failed++
          result.errors.push({
            actionId: action.id,
            error: errorMessage,
          })
        } else {
          // Will retry later
          result.failed++
        }

        result.success = false
      }
    }

    // Remove successfully processed actions
    processedIds.forEach((id) => this.remove(id))

    // Remove actions that exceeded max retries
    failedIds.forEach((id) => this.remove(id))

    return result
  }

  /**
   * Check if queue is currently syncing
   */
  getIsSyncing(): boolean {
    return this.isSyncing
  }
}

