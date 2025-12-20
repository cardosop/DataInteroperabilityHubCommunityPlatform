/**
 * useLogout Hook Tests
 *
 * Tests for the logout mutation hook.
 * These tests verify hook structure and mutation behavior.
 *
 * Note: These tests verify the hook's structure and behavior.
 * Full integration tests with a running backend are required for complete coverage.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useLogout } from '../useLogout'
import { createHookWrapper } from './test-utils'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

describe('useLogout', () => {
  beforeEach(() => {
    localStorageMock.clear()
    vi.clearAllMocks()
  })

  it('should return correct mutation structure', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useLogout(), { wrapper })

    expect(result.current).toHaveProperty('mutate')
    expect(result.current).toHaveProperty('mutateAsync')
    expect(result.current).toHaveProperty('isPending')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('isSuccess')
    expect(result.current).toHaveProperty('error')
  })

  it('should have mutate function', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useLogout(), { wrapper })

    expect(typeof result.current.mutate).toBe('function')
    expect(typeof result.current.mutateAsync).toBe('function')
  })

  it('should initially be in idle state', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useLogout(), { wrapper })

    expect(result.current.isPending).toBe(false)
    expect(result.current.isError).toBe(false)
    expect(result.current.isSuccess).toBe(false)
    expect(result.current.error).toBeNull()
  })
})

