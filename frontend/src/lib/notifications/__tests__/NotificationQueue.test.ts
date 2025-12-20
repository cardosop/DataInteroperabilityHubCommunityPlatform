/**
 * NotificationQueue Tests
 *
 * Comprehensive tests for the NotificationQueue class covering:
 * - Adding notifications
 * - Priority ordering
 * - Size limits
 * - Duplicate detection
 * - Cleanup of old notifications
 * - Mark as read functionality
 * - Filtering and querying
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { NotificationQueue, type Notification } from '../NotificationQueue'

describe('NotificationQueue', () => {
  let queue: NotificationQueue

  beforeEach(() => {
    queue = new NotificationQueue()
  })

  describe('Initialization', () => {
    it('should create empty queue', () => {
      expect(queue.getCount()).toBe(0)
      expect(queue.getAll()).toEqual([])
    })

    it('should use default options', () => {
      const defaultQueue = new NotificationQueue()
      expect(defaultQueue.getCount()).toBe(0)
    })

    it('should accept custom options', () => {
      const customQueue = new NotificationQueue({
        maxSize: 50,
        maxAge: 1000,
        allowDuplicates: true,
      })
      expect(customQueue.getCount()).toBe(0)
    })
  })

  describe('Adding Notifications', () => {
    it('should add notification to queue', () => {
      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      const added = queue.add(notification)
      expect(added).toBe(true)
      expect(queue.getCount()).toBe(1)
      expect(queue.get('1')).toEqual(notification)
    })

    it('should order notifications by priority', () => {
      const lowPriority: Notification = {
        id: '1',
        title: 'Low',
        message: 'Low priority',
        timestamp: new Date(),
        read: false,
        priority: 1,
      }

      const highPriority: Notification = {
        id: '2',
        title: 'High',
        message: 'High priority',
        timestamp: new Date(),
        read: false,
        priority: 10,
      }

      queue.add(lowPriority)
      queue.add(highPriority)

      const all = queue.getAll()
      expect(all[0].id).toBe('2') // High priority first
      expect(all[1].id).toBe('1') // Low priority second
    })

    it('should order by timestamp when priority is equal', () => {
      const older: Notification = {
        id: '1',
        title: 'Older',
        message: 'Older notification',
        timestamp: new Date(Date.now() - 1000),
        read: false,
        priority: 5,
      }

      const newer: Notification = {
        id: '2',
        title: 'Newer',
        message: 'Newer notification',
        timestamp: new Date(),
        read: false,
        priority: 5,
      }

      queue.add(older)
      queue.add(newer)

      const all = queue.getAll()
      expect(all[0].id).toBe('2') // Newer first
      expect(all[1].id).toBe('1') // Older second
    })
  })

  describe('Duplicate Detection', () => {
    it('should reject duplicate notifications by default', () => {
      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      queue.add(notification)
      const added = queue.add({ ...notification, id: '2' })

      expect(added).toBe(false)
      expect(queue.getCount()).toBe(1)
    })

    it('should allow duplicates when allowDuplicates is true', () => {
      const queueWithDuplicates = new NotificationQueue({ allowDuplicates: true })

      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      queueWithDuplicates.add(notification)
      const added = queueWithDuplicates.add({ ...notification, id: '2' })

      expect(added).toBe(true)
      expect(queueWithDuplicates.getCount()).toBe(2)
    })

    it('should only detect duplicates within duplicate window', () => {
      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(Date.now() - 10000), // 10 seconds ago
        read: false,
      }

      queue.add(notification)
      const added = queue.add({
        ...notification,
        id: '2',
        timestamp: new Date(), // Now
      })

      // Should allow since outside duplicate window (default 5 seconds)
      expect(added).toBe(true)
      expect(queue.getCount()).toBe(2)
    })
  })

  describe('Size Limits', () => {
    it('should enforce max size', () => {
      const limitedQueue = new NotificationQueue({ maxSize: 3 })

      for (let i = 0; i < 5; i++) {
        limitedQueue.add({
          id: `${i}`,
          title: `Test ${i}`,
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        })
      }

      expect(limitedQueue.getCount()).toBe(3)
    })

    it('should remove oldest non-persistent notifications when limit exceeded', () => {
      const limitedQueue = new NotificationQueue({ maxSize: 2 })

      const persistent: Notification = {
        id: 'persistent',
        title: 'Persistent',
        message: 'Persistent notification',
        timestamp: new Date(Date.now() - 1000),
        read: false,
        persistent: true,
      }

      limitedQueue.add(persistent)
      limitedQueue.add({
        id: '1',
        title: 'Test 1',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })
      limitedQueue.add({
        id: '2',
        title: 'Test 2',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      // Persistent should remain
      expect(limitedQueue.get('persistent')).toBeDefined()
      expect(limitedQueue.getCount()).toBe(2)
    })
  })

  describe('Mark as Read', () => {
    it('should mark notification as read', () => {
      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      queue.add(notification)
      const marked = queue.markAsRead('1')

      expect(marked).toBe(true)
      expect(queue.get('1')?.read).toBe(true)
      expect(queue.getUnreadCount()).toBe(0)
    })

    it('should mark all notifications as read', () => {
      queue.add({
        id: '1',
        title: 'Test 1',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })
      queue.add({
        id: '2',
        title: 'Test 2',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      queue.markAllAsRead()

      expect(queue.getUnreadCount()).toBe(0)
      expect(queue.get('1')?.read).toBe(true)
      expect(queue.get('2')?.read).toBe(true)
    })

    it('should return false when marking non-existent notification as read', () => {
      const marked = queue.markAsRead('non-existent')
      expect(marked).toBe(false)
    })
  })

  describe('Removing Notifications', () => {
    it('should remove notification', () => {
      queue.add({
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      const removed = queue.remove('1')
      expect(removed).toBe(true)
      expect(queue.getCount()).toBe(0)
    })

    it('should return false when removing non-existent notification', () => {
      const removed = queue.remove('non-existent')
      expect(removed).toBe(false)
    })

    it('should clear all notifications', () => {
      queue.add({
        id: '1',
        title: 'Test 1',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })
      queue.add({
        id: '2',
        title: 'Test 2',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      queue.clear()
      expect(queue.getCount()).toBe(0)
    })

    it('should clear only read notifications', () => {
      queue.add({
        id: '1',
        title: 'Test 1',
        message: 'Test message',
        timestamp: new Date(),
        read: true,
      })
      queue.add({
        id: '2',
        title: 'Test 2',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      queue.clearRead()
      expect(queue.getCount()).toBe(1)
      expect(queue.get('2')).toBeDefined()
    })
  })

  describe('Filtering and Querying', () => {
    it('should get unread notifications', () => {
      queue.add({
        id: '1',
        title: 'Test 1',
        message: 'Test message',
        timestamp: new Date(),
        read: true,
      })
      queue.add({
        id: '2',
        title: 'Test 2',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      const unread = queue.getUnread()
      expect(unread.length).toBe(1)
      expect(unread[0].id).toBe('2')
    })

    it('should get notifications by severity', () => {
      queue.add({
        id: '1',
        title: 'Error',
        message: 'Error message',
        timestamp: new Date(),
        read: false,
        severity: 'error',
      })
      queue.add({
        id: '2',
        title: 'Success',
        message: 'Success message',
        timestamp: new Date(),
        read: false,
        severity: 'success',
      })
      queue.add({
        id: '3',
        title: 'Error 2',
        message: 'Error message',
        timestamp: new Date(),
        read: false,
        severity: 'error',
      })

      const errors = queue.getBySeverity('error')
      expect(errors.length).toBe(2)
      expect(errors.every((n) => n.severity === 'error')).toBe(true)
    })

    it('should get unread count', () => {
      queue.add({
        id: '1',
        title: 'Test 1',
        message: 'Test message',
        timestamp: new Date(),
        read: true,
      })
      queue.add({
        id: '2',
        title: 'Test 2',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })
      queue.add({
        id: '3',
        title: 'Test 3',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      expect(queue.getUnreadCount()).toBe(2)
    })
  })

  describe('Subscriptions', () => {
    it('should notify listeners when queue changes', () => {
      const listener = vi.fn()
      const unsubscribe = queue.subscribe(listener)

      queue.add({
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      expect(listener).toHaveBeenCalledTimes(1)
      expect(listener).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ id: '1' })]))

      unsubscribe()
    })

    it('should allow multiple listeners', () => {
      const listener1 = vi.fn()
      const listener2 = vi.fn()

      queue.subscribe(listener1)
      queue.subscribe(listener2)

      queue.add({
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      expect(listener1).toHaveBeenCalledTimes(1)
      expect(listener2).toHaveBeenCalledTimes(1)
    })

    it('should stop notifying after unsubscribe', () => {
      const listener = vi.fn()
      const unsubscribe = queue.subscribe(listener)

      unsubscribe()

      queue.add({
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      })

      expect(listener).not.toHaveBeenCalled()
    })
  })
})

