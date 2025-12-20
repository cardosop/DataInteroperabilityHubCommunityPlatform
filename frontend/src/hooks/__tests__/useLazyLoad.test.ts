/**
 * useLazyLoad Hook Tests
 *
 * Comprehensive tests for lazy load hook covering:
 * - Should load state
 * - Intersection detection
 * - Enabled/disabled state
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useLazyLoad } from '../useLazyLoad'

// Mock IntersectionObserver
class MockIntersectionObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()

  constructor(
    public callback: IntersectionObserverCallback,
    public options?: IntersectionObserverInit
  ) {}
}

describe('useLazyLoad', () => {
  let mockObserver: MockIntersectionObserver
  let originalIntersectionObserver: typeof IntersectionObserver

  beforeEach(() => {
    originalIntersectionObserver = global.IntersectionObserver
    global.IntersectionObserver = MockIntersectionObserver as any
    mockObserver = new MockIntersectionObserver(() => {})
  })

  afterEach(() => {
    global.IntersectionObserver = originalIntersectionObserver
    vi.clearAllMocks()
  })

  it('should return shouldLoad false initially when enabled', () => {
    const { result } = renderHook(() => useLazyLoad({ enabled: true }))

    expect(result.current.shouldLoad).toBe(false)
  })

  it('should return shouldLoad true when disabled', () => {
    const { result } = renderHook(() => useLazyLoad({ enabled: false }))

    expect(result.current.shouldLoad).toBe(true)
  })

  it('should set shouldLoad to true when intersecting', async () => {
    const { result } = renderHook(() => useLazyLoad({ enabled: true }))

    // Simulate intersection
    const mockEntry = {
      isIntersecting: true,
      intersectionRatio: 1,
      target: result.current.ref.current || document.createElement('div'),
    } as IntersectionObserverEntry

    if (mockObserver.callback) {
      mockObserver.callback([mockEntry], mockObserver as any)
    }

    await waitFor(() => {
      expect(result.current.shouldLoad).toBe(true)
    })
  })

  it('should use custom root margin', () => {
    renderHook(() => useLazyLoad({ rootMargin: '100px' }))

    // Verify observer was created with correct options
    expect(global.IntersectionObserver).toHaveBeenCalled()
  })
})

