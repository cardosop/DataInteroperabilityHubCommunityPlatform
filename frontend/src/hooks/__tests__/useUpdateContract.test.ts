/**
 * useUpdateContract Hook Tests
 *
 * Tests for the update contract mutation hook.
 * These tests verify hook structure and mutation behavior.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useUpdateContract } from '../useUpdateContract'
import { createHookWrapper } from './test-utils'
import * as contractsApi from '@/lib/api/contracts'

// Mock the contracts API
vi.mock('@/lib/api/contracts', () => ({
  updateContract: vi.fn(),
}))

describe('useUpdateContract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct mutation structure', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useUpdateContract(), { wrapper })

    expect(result.current).toHaveProperty('mutate')
    expect(result.current).toHaveProperty('mutateAsync')
    expect(result.current).toHaveProperty('isPending')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('isSuccess')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('data')
  })

  it('should initially be in idle state', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useUpdateContract(), { wrapper })

    expect(result.current.isPending).toBe(false)
    expect(result.current.isError).toBe(false)
    expect(result.current.isSuccess).toBe(false)
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toBeNull()
  })
})

