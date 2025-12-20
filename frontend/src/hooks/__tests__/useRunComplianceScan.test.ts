/**
 * useRunComplianceScan Hook Tests
 *
 * Tests for the run compliance scan mutation hook.
 * These tests verify hook structure and mutation behavior.
 *
 * Note: These tests verify the hook's structure and behavior.
 * Full integration tests with a running backend are required for complete coverage.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useRunComplianceScan } from '../useRunComplianceScan'
import { createHookWrapper } from './test-utils'
import * as complianceApi from '@/lib/api/compliance'

// Mock the compliance API
vi.mock('@/lib/api/compliance', () => ({
  runComplianceScan: vi.fn(),
}))

describe('useRunComplianceScan', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct mutation structure', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useRunComplianceScan(), { wrapper })

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
    const { result } = renderHook(() => useRunComplianceScan(), { wrapper })

    expect(result.current.isPending).toBe(false)
    expect(result.current.isError).toBe(false)
    expect(result.current.isSuccess).toBe(false)
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toBeNull()
  })
})

