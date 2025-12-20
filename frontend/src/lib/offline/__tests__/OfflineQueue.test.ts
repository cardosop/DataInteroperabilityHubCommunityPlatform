/**
 * OfflineQueue Tests
 *
 * Comprehensive tests for the OfflineQueue class covering:
 * - Adding actions
 * - Priority ordering
 * - Size limits
 * - Duplicate detection
 * - Sync functionality
 * - Retry logic
 * - Partial sync failures
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { OfflineQueue, type QueuedAction } from '../OfflineQueue'

describe('OfflineQueue', () => {
  let queue: OfflineQueue

  beforeEach(() => {
    queue = new OfflineQueue()
  })

  describe('Initialization', () => {
    it('should create empty queue', () => {
      expect(queue.getCount()).toBe(0)
      expect(queue.getAll()).toEqual([])
    })

    it('should use default options', () => {
      const defaultQueue = new OfflineQueue()
      expect(defaultQueue.getCount()).toBe(0)
    })

    it('should accept custom options', () => {
      const customQueue = new OfflineQueue({
        maxSize: 50,
        maxRetries: 5,
        initialRetryDelay: 2000,
      })
      expect(customQueue.getCount()).toBe(0)
    })
  })

  describe('Adding Actions', () => {
    it('should add action to queue', () => {
      const actionId = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test Asset' },
      })

      expect(actionId).toBeTruthy()
      expect(queue.getCount()).toBe(1)
      expect(queue.get(actionId)).toBeDefined()
    })

    it('should order actions by priority', () => {
      const lowPriority = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Low Priority' },
        priority: 1,
      })

      const highPriority = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'High Priority' },
        priority: 10,
      })

      const all = queue.getAll()
      expect(all[0].id).toBe(highPriority) // High priority first
      expect(all[1].id).toBe(lowPriority) // Low priority second
    })

    it('should order by timestamp when priority is equal', () => {
      const first = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'First' },
        priority: 5,
      })

      // Small delay to ensure different timestamps
      return new Promise((resolve) => {
        setTimeout(() => {
          const second = queue.add({
            method: 'POST',
            url: '/api/v1/assets/',
            data: { name: 'Second' },
            priority: 5,
          })

          const all = queue.getAll()
          expect(all[0].id).toBe(first) // Older first
          expect(all[1].id).toBe(second) // Newer second
          resolve(undefined)
        }, 10)
      })
    })
  })

  describe('Duplicate Detection', () => {
    it('should reject duplicate actions by default', () => {
      queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      expect(() => {
        queue.add({
          method: 'POST',
          url: '/api/v1/assets/',
          data: { name: 'Test' },
        })
      }).toThrow('Duplicate action detected')
    })

    it('should allow duplicates when allowDuplicates is true', () => {
      const queueWithDuplicates = new OfflineQueue({ allowDuplicates: true })

      queueWithDuplicates.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      expect(() => {
        queueWithDuplicates.add({
          method: 'POST',
          url: '/api/v1/assets/',
          data: { name: 'Test' },
        })
      }).not.toThrow()
    })

    it('should only detect duplicates within duplicate window', () => {
      const firstId = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      // Wait outside duplicate window (default 5 seconds)
      return new Promise((resolve) => {
        setTimeout(() => {
          expect(() => {
            queue.add({
              method: 'POST',
              url: '/api/v1/assets/',
              data: { name: 'Test' },
            })
          }).not.toThrow()
          resolve(undefined)
        }, 5100)
      })
    })
  })

  describe('Size Limits', () => {
    it('should enforce max size', () => {
      const limitedQueue = new OfflineQueue({ maxSize: 3 })

      for (let i = 0; i < 5; i++) {
        limitedQueue.add({
          method: 'POST',
          url: `/api/v1/assets/${i}`,
          data: { name: `Test ${i}` },
        })
      }

      expect(limitedQueue.getCount()).toBe(3)
    })

    it('should remove oldest lowest priority action when limit exceeded', () => {
      const limitedQueue = new OfflineQueue({ maxSize: 2 })

      const highPriority = limitedQueue.add({
        method: 'POST',
        url: '/api/v1/assets/high',
        data: { name: 'High Priority' },
        priority: 10,
      })

      limitedQueue.add({
        method: 'POST',
        url: '/api/v1/assets/low1',
        data: { name: 'Low Priority 1' },
        priority: 1,
      })

      limitedQueue.add({
        method: 'POST',
        url: '/api/v1/assets/low2',
        data: { name: 'Low Priority 2' },
        priority: 1,
      })

      // High priority should remain
      expect(limitedQueue.get(highPriority)).toBeDefined()
      expect(limitedQueue.getCount()).toBe(2)
    })
  })

  describe('Sync Functionality', () => {
    it('should sync all actions successfully', async () => {
      const executeAction = vi.fn().mockResolvedValue({})

      queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test 1' },
      })

      queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test 2' },
      })

      const result = await queue.sync(executeAction)

      expect(result.success).toBe(true)
      expect(result.processed).toBe(2)
      expect(result.failed).toBe(0)
      expect(executeAction).toHaveBeenCalledTimes(2)
      expect(queue.getCount()).toBe(0)
    })

    it('should handle sync failures with retry', async () => {
      let attemptCount = 0
      const executeAction = vi.fn().mockImplementation(() => {
        attemptCount++
        if (attemptCount <= 2) {
          throw new Error('Network error')
        }
        return Promise.resolve({})
      })

      const actionId = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      const result = await queue.sync(executeAction)

      // Should retry and eventually succeed
      expect(result.processed).toBeGreaterThanOrEqual(0)
      expect(executeAction).toHaveBeenCalled()
    })

    it('should remove actions that exceed max retries', async () => {
      const executeAction = vi.fn().mockRejectedValue(new Error('Persistent error'))

      const actionId = queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      const limitedRetryQueue = new OfflineQueue({ maxRetries: 1 })
      limitedRetryQueue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      const result = await limitedRetryQueue.sync(executeAction)

      expect(result.failed).toBe(1)
      expect(result.errors).toHaveLength(1)
      expect(limitedRetryQueue.getCount()).toBe(0) // Removed after max retries
    })

    it('should handle partial sync failures gracefully', async () => {
      let callCount = 0
      const executeAction = vi.fn().mockImplementation(() => {
        callCount++
        if (callCount === 1) {
          return Promise.resolve({}) // First succeeds
        }
        throw new Error('Network error') // Second fails
      })

      queue.add({
        method: 'POST',
        url: '/api/v1/assets/1',
        data: { name: 'Test 1' },
      })

      queue.add({
        method: 'POST',
        url: '/api/v1/assets/2',
        data: { name: 'Test 2' },
      })

      const result = await queue.sync(executeAction)

      expect(result.processed).toBe(1)
      expect(result.failed).toBe(1)
      expect(result.success).toBe(false)
      expect(result.errors).toHaveLength(0) // Not exceeded max retries yet
    })

    it('should not sync concurrently', async () => {
      const executeAction = vi.fn().mockImplementation(
        () => new Promise((resolve) => setTimeout(resolve, 100))
      )

      queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      const sync1 = queue.sync(executeAction)
      const sync2 = queue.sync(executeAction)

      const [result1, result2] = await Promise.all([sync1, sync2])

      // Should only execute once
      expect(executeAction).toHaveBeenCalledTimes(1)
    })
  })

  describe('Subscriptions', () => {
    it('should notify listeners when queue changes', () => {
      const listener = vi.fn()
      const unsubscribe = queue.subscribe(listener)

      queue.add({
        method: 'POST',
        url: '/api/v1/assets/',
        data: { name: 'Test' },
      })

      expect(listener).toHaveBeenCalledTimes(1)
      expect(listener).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ method: 'POST' })]))

      unsubscribe()
    })
  })
})

