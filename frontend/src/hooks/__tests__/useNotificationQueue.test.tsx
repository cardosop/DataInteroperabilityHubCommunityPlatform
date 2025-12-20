/**
 * useNotificationQueue Hook Tests
 *
 * Comprehensive tests for the useNotificationQueue hook covering:
 * - Queue initialization
 * - Adding notifications
 * - Persistence
 * - Auto-dismiss
 * - Queue management
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useNotificationQueue } from '../useNotificationQueue'
import type { Notification } from '@/lib/notifications/NotificationQueue'

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

describe('useNotificationQueue', () => {
  beforeEach(() => {
    localStorageMock.clear()
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    })
  })

  describe('Initialization', () => {
    it('should initialize with empty queue', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      expect(result.current.notifications).toEqual([])
      expect(result.current.unreadCount).toBe(0)
    })

    it('should load persisted notifications', () => {
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

      localStorageMock.setItem('notifications', JSON.stringify(stored))

      const { result } = renderHook(() => useNotificationQueue({ persist: true }))

      expect(result.current.notifications).toHaveLength(1)
      expect(result.current.notifications[0].id).toBe('1')
    })
  })

  describe('Adding Notifications', () => {
    it('should add notification to queue', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      act(() => {
        result.current.add(notification)
      })

      expect(result.current.notifications).toHaveLength(1)
      expect(result.current.notifications[0].id).toBe('1')
    })

    it('should persist notification when persist is enabled', async () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: true }))

      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      act(() => {
        result.current.add(notification)
      })

      await waitFor(() => {
        const stored = localStorageMock.getItem('notifications')
        expect(stored).toBeTruthy()
        const parsed = JSON.parse(stored!)
        expect(parsed.notifications).toHaveLength(1)
      })
    })
  })

  describe('Removing Notifications', () => {
    it('should remove notification', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      act(() => {
        result.current.add(notification)
        result.current.remove('1')
      })

      expect(result.current.notifications).toHaveLength(0)
    })
  })

  describe('Mark as Read', () => {
    it('should mark notification as read', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
      }

      act(() => {
        result.current.add(notification)
        result.current.markAsRead('1')
      })

      expect(result.current.notifications[0].read).toBe(true)
      expect(result.current.unreadCount).toBe(0)
    })

    it('should mark all notifications as read', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      act(() => {
        result.current.add({
          id: '1',
          title: 'Test 1',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        })
        result.current.add({
          id: '2',
          title: 'Test 2',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        })
        result.current.markAllAsRead()
      })

      expect(result.current.unreadCount).toBe(0)
    })
  })

  describe('Auto-dismiss', () => {
    it('should auto-dismiss notification after delay', async () => {
      vi.useFakeTimers()

      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      const notification: Notification = {
        id: '1',
        title: 'Test',
        message: 'Test message',
        timestamp: new Date(),
        read: false,
        autoDismiss: 1000,
      }

      act(() => {
        result.current.add(notification)
      })

      expect(result.current.notifications).toHaveLength(1)

      act(() => {
        vi.advanceTimersByTime(1000)
      })

      await waitFor(() => {
        expect(result.current.notifications).toHaveLength(0)
      })

      vi.useRealTimers()
    })
  })

  describe('Clear Operations', () => {
    it('should clear all notifications', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      act(() => {
        result.current.add({
          id: '1',
          title: 'Test 1',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        })
        result.current.add({
          id: '2',
          title: 'Test 2',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        })
        result.current.clear()
      })

      expect(result.current.notifications).toHaveLength(0)
    })

    it('should clear only read notifications', () => {
      const { result } = renderHook(() => useNotificationQueue({ persist: false }))

      act(() => {
        result.current.add({
          id: '1',
          title: 'Test 1',
          message: 'Test message',
          timestamp: new Date(),
          read: true,
        })
        result.current.add({
          id: '2',
          title: 'Test 2',
          message: 'Test message',
          timestamp: new Date(),
          read: false,
        })
        result.current.clearRead()
      })

      expect(result.current.notifications).toHaveLength(1)
      expect(result.current.notifications[0].id).toBe('2')
    })
  })
})

