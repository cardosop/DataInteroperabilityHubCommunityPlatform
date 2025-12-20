/**
 * useNetworkStatus Hook Tests
 *
 * Comprehensive tests for the useNetworkStatus hook covering:
 * - Online/offline detection
 * - Network quality detection
 * - Connection type detection
 * - Event handling
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useNetworkStatus } from '../useNetworkStatus'

describe('useNetworkStatus', () => {
  beforeEach(() => {
    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      configurable: true,
      value: true,
    })

    // Mock NetworkInformation API if available
    if ('connection' in navigator) {
      Object.defineProperty(navigator, 'connection', {
        writable: true,
        configurable: true,
        value: {
          effectiveType: '4g',
          downlink: 10,
          rtt: 50,
          saveData: false,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
        },
      })
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initial State', () => {
    it('should detect online status initially', () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        configurable: true,
        value: true,
      })

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.isOnline).toBe(true)
      expect(result.current.isOffline).toBe(false)
    })

    it('should detect offline status initially', () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        configurable: true,
        value: false,
      })

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.isOnline).toBe(false)
      expect(result.current.isOffline).toBe(true)
    })
  })

  describe('Online/Offline Events', () => {
    it('should update when going offline', () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        configurable: true,
        value: true,
      })

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.isOnline).toBe(true)

      // Simulate going offline
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          writable: true,
          configurable: true,
          value: false,
        })
        window.dispatchEvent(new Event('offline'))
      })

      expect(result.current.isOnline).toBe(false)
      expect(result.current.isOffline).toBe(true)
    })

    it('should update when coming back online', () => {
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        configurable: true,
        value: false,
      })

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.isOffline).toBe(true)

      // Simulate coming back online
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          writable: true,
          configurable: true,
          value: true,
        })
        window.dispatchEvent(new Event('online'))
      })

      expect(result.current.isOnline).toBe(true)
      expect(result.current.isOffline).toBe(false)
    })
  })

  describe('Network Quality', () => {
    it('should detect slow network', () => {
      if ('connection' in navigator) {
        Object.defineProperty(navigator, 'connection', {
          writable: true,
          configurable: true,
          value: {
            effectiveType: '2g',
            downlink: 0.5,
            rtt: 2000,
            saveData: false,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
          },
        })
      }

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.effectiveType).toBe('2g')
      expect(result.current.isSlowConnection).toBe(true)
    })

    it('should detect fast network', () => {
      if ('connection' in navigator) {
        Object.defineProperty(navigator, 'connection', {
          writable: true,
          configurable: true,
          value: {
            effectiveType: '4g',
            downlink: 10,
            rtt: 50,
            saveData: false,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
          },
        })
      }

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.effectiveType).toBe('4g')
      expect(result.current.isSlowConnection).toBe(false)
    })
  })

  describe('Save Data Mode', () => {
    it('should detect save data mode', () => {
      if ('connection' in navigator) {
        Object.defineProperty(navigator, 'connection', {
          writable: true,
          configurable: true,
          value: {
            effectiveType: '4g',
            downlink: 10,
            rtt: 50,
            saveData: true,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
          },
        })
      }

      const { result } = renderHook(() => useNetworkStatus())

      expect(result.current.saveData).toBe(true)
    })
  })
})

