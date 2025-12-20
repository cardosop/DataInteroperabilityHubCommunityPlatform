/**
 * useIntersectionObserver Hook Tests
 *
 * Comprehensive tests for intersection observer hook covering:
 * - Basic intersection detection
 * - Callbacks (onEnter, onLeave, onIntersect)
 * - Once mode
 * - Multiple elements
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useIntersectionObserver, useMultipleIntersectionObserver } from '../useIntersectionObserver'

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

describe('useIntersectionObserver', () => {
  let mockObserver: MockIntersectionObserver | null = null
  let originalIntersectionObserver: typeof IntersectionObserver

  beforeEach(() => {
    originalIntersectionObserver = global.IntersectionObserver
    // Capture the observer instance when it's created
    global.IntersectionObserver = class extends MockIntersectionObserver {
      constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
        super(callback, options)
        mockObserver = this
      }
    } as any
  })

  afterEach(() => {
    global.IntersectionObserver = originalIntersectionObserver
    mockObserver = null
    vi.clearAllMocks()
  })

  it('should observe element when enabled', () => {
    const { result } = renderHook(() => useIntersectionObserver({ enabled: true }))

    expect(result.current.ref).toBeDefined()
    expect(result.current.isIntersecting).toBe(false)
  })

  it('should not observe when disabled', () => {
    const { result } = renderHook(() => useIntersectionObserver({ enabled: false }))

    expect(result.current.isIntersecting).toBe(false)
  })

  it('should call onEnter when element enters viewport', async () => {
    const onEnter = vi.fn()
    const { result } = renderHook(() =>
      useIntersectionObserver({
        onEnter,
      })
    )

    // Attach ref to an element so observer is created
    const element = document.createElement('div')
    result.current.ref.current = element

    // Wait for observer to be created
    await waitFor(() => {
      expect(mockObserver).not.toBeNull()
    })

    // Simulate intersection
    const mockEntry = {
      isIntersecting: true,
      intersectionRatio: 1,
      target: element,
    } as IntersectionObserverEntry

    if (mockObserver?.callback) {
      mockObserver.callback([mockEntry], mockObserver as any)
    }

    await waitFor(() => {
      expect(onEnter).toHaveBeenCalled()
    })
  })

  it('should call onLeave when element leaves viewport', async () => {
    const onLeave = vi.fn()
    const { result } = renderHook(() =>
      useIntersectionObserver({
        onLeave,
      })
    )

    // Attach ref to an element so observer is created
    const element = document.createElement('div')
    result.current.ref.current = element

    // Wait for observer to be created
    await waitFor(() => {
      expect(mockObserver).not.toBeNull()
    })

    // First simulate entering (so hasIntersectedRef is set)
    const enterEntry = {
      isIntersecting: true,
      intersectionRatio: 1,
      target: element,
    } as IntersectionObserverEntry

    if (mockObserver?.callback) {
      mockObserver.callback([enterEntry], mockObserver as any)
    }

    // Then simulate leaving
    const leaveEntry = {
      isIntersecting: false,
      intersectionRatio: 0,
      target: element,
    } as IntersectionObserverEntry

    if (mockObserver?.callback) {
      mockObserver.callback([leaveEntry], mockObserver as any)
    }

    await waitFor(() => {
      expect(onLeave).toHaveBeenCalled()
    })
  })

  it('should disconnect after first intersection when once is true', async () => {
    const { result } = renderHook(() =>
      useIntersectionObserver({
        once: true,
      })
    )

    // Attach ref to an element so observer is created
    const element = document.createElement('div')
    result.current.ref.current = element

    // Wait for observer to be created
    await waitFor(() => {
      expect(mockObserver).not.toBeNull()
    })

    const mockEntry = {
      isIntersecting: true,
      intersectionRatio: 1,
      target: element,
    } as IntersectionObserverEntry

    if (mockObserver?.callback) {
      mockObserver.callback([mockEntry], mockObserver as any)
    }

    await waitFor(() => {
      expect(mockObserver?.disconnect).toHaveBeenCalled()
    })
  })

  it('should update intersection ratio', async () => {
    const { result } = renderHook(() => useIntersectionObserver())

    // Attach ref to an element so observer is created
    const element = document.createElement('div')
    result.current.ref.current = element

    // Wait for observer to be created
    await waitFor(() => {
      expect(mockObserver).not.toBeNull()
    })

    const mockEntry = {
      isIntersecting: true,
      intersectionRatio: 0.5,
      target: element,
    } as IntersectionObserverEntry

    if (mockObserver?.callback) {
      mockObserver.callback([mockEntry], mockObserver as any)
    }

    await waitFor(() => {
      expect(result.current.intersectionRatio).toBe(0.5)
    })
  })
})

describe('useMultipleIntersectionObserver', () => {
  it('should observe multiple elements', () => {
    const refs = [
      { current: document.createElement('div') },
      { current: document.createElement('div') },
    ]

    const { result } = renderHook(() =>
      useMultipleIntersectionObserver(refs as any, {})
    )

    expect(result.current).toHaveLength(2)
  })
})

