/**
 * useVirtualizer Hook Tests
 *
 * Comprehensive tests for useVirtualizer hook covering:
 * - Virtualizer creation
 * - Virtual items calculation
 * - Scroll functions
 * - Measure element
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useVirtualizer } from '../useVirtualizer'

// Mock @tanstack/react-virtual
const mockVirtualizer = {
  getVirtualItems: vi.fn(() => [
    { key: 0, index: 0, start: 0, size: 50 },
    { key: 1, index: 1, start: 50, size: 50 },
  ]),
  getTotalSize: vi.fn(() => 100),
  scrollToIndex: vi.fn(),
  scrollToOffset: vi.fn(),
  measureElement: vi.fn(),
  scrollOffset: 0,
}

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: vi.fn(() => mockVirtualizer),
}))

describe('useVirtualizer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should create virtualizer with fixed height', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        itemHeight: 50,
      })
    )

    expect(result.current.virtualizer).toBeDefined()
    expect(result.current.parentRef).toBeDefined()
    expect(result.current.virtualItems).toBeDefined()
    expect(result.current.totalSize).toBe(100)
  })

  it('should create virtualizer with variable height', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        getItemHeight: (index) => index * 10 + 50,
        estimateSize: 50,
      })
    )

    expect(result.current.virtualizer).toBeDefined()
    expect(result.current.virtualItems).toBeDefined()
  })

  it('should provide scrollToIndex function', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        itemHeight: 50,
      })
    )

    result.current.scrollToIndex(5, { align: 'center' })
    expect(mockVirtualizer.scrollToIndex).toHaveBeenCalledWith(5, {
      align: 'center',
    })
  })

  it('should provide scrollToOffset function', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        itemHeight: 50,
      })
    )

    result.current.scrollToOffset(100, { align: 'start' })
    expect(mockVirtualizer.scrollToOffset).toHaveBeenCalledWith(100, {
      align: 'start',
    })
  })

  it('should provide measureElement function', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        itemHeight: 50,
      })
    )

    const element = document.createElement('div')
    result.current.measureElement(element)
    expect(mockVirtualizer.measureElement).toHaveBeenCalledWith(element)
  })

  it('should handle disabled state', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        itemHeight: 50,
        enabled: false,
      })
    )

    expect(result.current.virtualizer).toBeDefined()
  })

  it('should handle horizontal scrolling', () => {
    const { result } = renderHook(() =>
      useVirtualizer({
        count: 10,
        itemHeight: 50,
        horizontal: true,
      })
    )

    expect(result.current.virtualizer).toBeDefined()
  })
})

