/**
 * NotificationPersistence Tests
 *
 * Comprehensive tests for the NotificationPersistence service covering:
 * - Saving notifications
 * - Loading notifications
 * - Clearing notifications
 * - Version migration
 * - Error handling
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { NotificationPersistence } from '../NotificationPersistence'
import type { Notification } from '../NotificationQueue'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString()
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
  }
})()

describe('NotificationPersistence', () => {
  let persistence: NotificationPersistence

  beforeEach(() => {
    persistence = new NotificationPersistence('test-notifications')
    localStorageMock.clear()
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    })
  })

  describe('Saving Notifications', () => {
    it('should save notifications to localStorage', () => {
      const notifications: Notification[] = [
        {
          id: '1',
          title: 'Test',
          message: 'Test message',
          timestamp: new Date('2024-01-01T00:00:00Z'),
          read: false,
        },
      ]

      const saved = persistence.save(notifications)
      expect(saved).toBe(true)

      const stored = localStorageMock.getItem('test-notifications')
      expect(stored).toBeTruthy()

      const parsed = JSON.parse(stored!)
      expect(parsed.version).toBe(1)
      expect(parsed.notifications).toHaveLength(1)
      expect(parsed.notifications[0].id).toBe('1')
    })

    it('should save multiple notifications', () => {
      const notifications: Notification[] = [
        {
          id: '1',
          title: 'Test 1',
          message: 'Test message 1',
          timestamp: new Date('2024-01-01T00:00:00Z'),
          read: false,
        },
        {
          id: '2',
          title: 'Test 2',
          message: 'Test message 2',
          timestamp: new Date('2024-01-02T00:00:00Z'),
          read: true,
        },
      ]

      persistence.save(notifications)

      const stored = localStorageMock.getItem('test-notifications')
      const parsed = JSON.parse(stored!)
      expect(parsed.notifications).toHaveLength(2)
    })

    it('should save notification with all properties', () => {
      const notifications: Notification[] = [
        {
          id: '1',
          title: 'Test',
          message: 'Test message',
          severity: 'error',
          timestamp: new Date('2024-01-01T00:00:00Z'),
          read: false,
          persistent: true,
          priority: 10,
          autoDismiss: 5000,
          metadata: { key: 'value' },
          action: {
            label: 'Action',
            onClick: () => {},
          },
        },
      ]

      persistence.save(notifications)

      const stored = localStorageMock.getItem('test-notifications')
      const parsed = JSON.parse(stored!)
      const notification = parsed.notifications[0]

      expect(notification.severity).toBe('error')
      expect(notification.persistent).toBe(true)
      expect(notification.priority).toBe(10)
      expect(notification.autoDismiss).toBe(5000)
      expect(notification.metadata).toEqual({ key: 'value' })
      expect(notification.action.label).toBe('Action')
    })

    it('should handle save errors gracefully', () => {
      // Mock localStorage.setItem to throw
      const originalSetItem = localStorageMock.setItem
      localStorageMock.setItem = vi.fn(() => {
        throw new Error('Storage quota exceeded')
      })

      const notifications: Notification[] = [
        {
          id: '1',
          title: 'Test',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        },
      ]

      const saved = persistence.save(notifications)
      expect(saved).toBe(false)

      // Restore
      localStorageMock.setItem = originalSetItem
    })
  })

  describe('Loading Notifications', () => {
    it('should load notifications from localStorage', () => {
      const stored = {
        version: 1,
        notifications: [
          {
            id: '1',
            title: 'Test',
            message: 'Test message',
            timestamp: '2024-01-01T00:00:00.000Z',
            read: false,
          },
        ],
        lastSaved: '2024-01-01T00:00:00.000Z',
      }

      localStorageMock.setItem('test-notifications', JSON.stringify(stored))

      const loaded = persistence.load()
      expect(loaded).toHaveLength(1)
      expect(loaded[0].id).toBe('1')
      expect(loaded[0].title).toBe('Test')
      expect(loaded[0].timestamp).toBeInstanceOf(Date)
    })

    it('should return empty array when no stored data', () => {
      const loaded = persistence.load()
      expect(loaded).toEqual([])
    })

    it('should handle invalid JSON gracefully', () => {
      localStorageMock.setItem('test-notifications', 'invalid json')

      const loaded = persistence.load()
      expect(loaded).toEqual([])
    })

    it('should restore notification with all properties', () => {
      const stored = {
        version: 1,
        notifications: [
          {
            id: '1',
            title: 'Test',
            message: 'Test message',
            severity: 'error',
            timestamp: '2024-01-01T00:00:00.000Z',
            read: false,
            persistent: true,
            priority: 10,
            autoDismiss: 5000,
            metadata: { key: 'value' },
            action: {
              label: 'Action',
            },
          },
        ],
        lastSaved: '2024-01-01T00:00:00.000Z',
      }

      localStorageMock.setItem('test-notifications', JSON.stringify(stored))

      const loaded = persistence.load()
      expect(loaded[0].severity).toBe('error')
      expect(loaded[0].persistent).toBe(true)
      expect(loaded[0].priority).toBe(10)
      expect(loaded[0].autoDismiss).toBe(5000)
      expect(loaded[0].metadata).toEqual({ key: 'value' })
      expect(loaded[0].action?.label).toBe('Action')
    })

    it('should handle version mismatch', () => {
      const stored = {
        version: 2, // Different version
        notifications: [
          {
            id: '1',
            title: 'Test',
            message: 'Test message',
            timestamp: '2024-01-01T00:00:00.000Z',
            read: false,
          },
        ],
        lastSaved: '2024-01-01T00:00:00.000Z',
      }

      localStorageMock.setItem('test-notifications', JSON.stringify(stored))

      // Should still load but warn
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const loaded = persistence.load()
      expect(loaded).toHaveLength(1)
      expect(consoleSpy).toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('Clearing Notifications', () => {
    it('should clear persisted notifications', () => {
      const stored = {
        version: 1,
        notifications: [
          {
            id: '1',
            title: 'Test',
            message: 'Test message',
            timestamp: '2024-01-01T00:00:00.000Z',
            read: false,
          },
        ],
        lastSaved: '2024-01-01T00:00:00.000Z',
      }

      localStorageMock.setItem('test-notifications', JSON.stringify(stored))
      expect(localStorageMock.getItem('test-notifications')).toBeTruthy()

      const cleared = persistence.clear()
      expect(cleared).toBe(true)
      expect(localStorageMock.getItem('test-notifications')).toBeNull()
    })
  })

  describe('Storage Size', () => {
    it('should calculate storage size', () => {
      const notifications: Notification[] = [
        {
          id: '1',
          title: 'Test',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        },
      ]

      persistence.save(notifications)
      const size = persistence.getStorageSize()
      expect(size).toBeGreaterThan(0)
    })

    it('should return 0 when no stored data', () => {
      const size = persistence.getStorageSize()
      expect(size).toBe(0)
    })
  })
})

