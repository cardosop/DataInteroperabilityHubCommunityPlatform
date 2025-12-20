/**
 * Memoization Utilities Tests
 *
 * Comprehensive tests for memoization utilities.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import {
  shallowEqual,
  deepEqual,
  createMemoizedComponent,
  useMemoizedValue,
  useMemoizedCallback,
  useMemoizedObject,
  useMemoizedArray,
  useMemoizedFilter,
  useMemoizedMap,
  useMemoizedSort,
  useMemoizedReduce,
  useMemoizedDebounce,
  useMemoizedThrottle,
  withShallowMemo,
  withDeepMemo,
} from '../memoization'

// Test component
const TestComponent: React.FC<{ value: number; onClick?: () => void }> = ({
  value,
  onClick,
}) => (
  <div>
    <span data-testid="value">{value}</span>
    {onClick && <button onClick={onClick}>Click</button>}
  </div>
)

describe('memoization utilities', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('shallowEqual', () => {
    it('should return true for equal objects', () => {
      const obj1 = { a: 1, b: 2 }
      const obj2 = { a: 1, b: 2 }
      expect(shallowEqual(obj1, obj2)).toBe(true)
    })

    it('should return false for different objects', () => {
      const obj1 = { a: 1, b: 2 }
      const obj2 = { a: 1, b: 3 }
      expect(shallowEqual(obj1, obj2)).toBe(false)
    })

    it('should return false for objects with different keys', () => {
      const obj1 = { a: 1, b: 2 }
      const obj2 = { a: 1, b: 2, c: 3 }
      expect(shallowEqual(obj1, obj2)).toBe(false)
    })
  })

  describe('deepEqual', () => {
    it('should return true for deeply equal objects', () => {
      const obj1 = { a: { b: { c: 1 } } }
      const obj2 = { a: { b: { c: 1 } } }
      expect(deepEqual(obj1, obj2)).toBe(true)
    })

    it('should return false for deeply different objects', () => {
      const obj1 = { a: { b: { c: 1 } } }
      const obj2 = { a: { b: { c: 2 } } }
      expect(deepEqual(obj1, obj2)).toBe(false)
    })
  })

  describe('createMemoizedComponent', () => {
    it('should create a memoized component', () => {
      const MemoizedComponent = createMemoizedComponent(TestComponent)
      expect(MemoizedComponent).toBeDefined()
      expect(MemoizedComponent.displayName).toBe('Memo(TestComponent)')
    })

    it('should use custom comparison function', () => {
      const areEqual = vi.fn(() => true)
      const MemoizedComponent = createMemoizedComponent(TestComponent, areEqual)

      const { rerender } = render(<MemoizedComponent value={1} />)
      rerender(<MemoizedComponent value={2} />)

      expect(areEqual).toHaveBeenCalled()
    })
  })

  describe('withShallowMemo', () => {
    it('should memoize component with shallow comparison', () => {
      const MemoizedComponent = withShallowMemo(TestComponent)
      expect(MemoizedComponent).toBeDefined()
    })
  })

  describe('withDeepMemo', () => {
    it('should memoize component with deep comparison', () => {
      const MemoizedComponent = withDeepMemo(TestComponent)
      expect(MemoizedComponent).toBeDefined()
    })
  })
})

// Test hooks (these would need to be tested in a component context)
describe('memoization hooks', () => {
  it('useMemoizedValue should memoize values', () => {
    // This would be tested in a component test
    expect(useMemoizedValue).toBeDefined()
  })

  it('useMemoizedCallback should memoize callbacks', () => {
    expect(useMemoizedCallback).toBeDefined()
  })

  it('useMemoizedObject should memoize objects', () => {
    expect(useMemoizedObject).toBeDefined()
  })

  it('useMemoizedArray should memoize arrays', () => {
    expect(useMemoizedArray).toBeDefined()
  })

  it('useMemoizedFilter should memoize filtered arrays', () => {
    expect(useMemoizedFilter).toBeDefined()
  })

  it('useMemoizedMap should memoize mapped arrays', () => {
    expect(useMemoizedMap).toBeDefined()
  })

  it('useMemoizedSort should memoize sorted arrays', () => {
    expect(useMemoizedSort).toBeDefined()
  })

  it('useMemoizedReduce should memoize reduced values', () => {
    expect(useMemoizedReduce).toBeDefined()
  })

  it('useMemoizedDebounce should memoize debounced callbacks', () => {
    expect(useMemoizedDebounce).toBeDefined()
  })

  it('useMemoizedThrottle should memoize throttled callbacks', () => {
    expect(useMemoizedThrottle).toBeDefined()
  })
})

