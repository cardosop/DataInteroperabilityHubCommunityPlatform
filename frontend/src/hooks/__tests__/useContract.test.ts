/**
 * useContract Hook Tests
 *
 * Tests for the single contract query hook.
 * These tests verify hook structure and query behavior.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useContract } from '../useContract'
import { createHookWrapper } from './test-utils'
import * as contractsApi from '@/lib/api/contracts'

// Mock the contracts API
vi.mock('@/lib/api/contracts', () => ({
  getContract: vi.fn(),
}))

describe('useContract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct query structure', () => {
    const mockGetContract = vi.mocked(contractsApi.getContract)
    mockGetContract.mockResolvedValue({
      id: '1',
      hub_contract_json: { hub_contract_version: '1.0.0', id: 'contract-1' },
      status: 'ACTIVE',
      normalization_status: 'NORMALIZED_OK',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })

    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useContract('1'), { wrapper })

    expect(result.current).toHaveProperty('data')
    expect(result.current).toHaveProperty('isLoading')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('refetch')
  })

  it('should call getContract with id', async () => {
    const mockGetContract = vi.mocked(contractsApi.getContract)
    const mockContract = {
      id: '1',
      hub_contract_json: { hub_contract_version: '1.0.0', id: 'contract-1' },
      status: 'ACTIVE',
      normalization_status: 'NORMALIZED_OK',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }
    mockGetContract.mockResolvedValue(mockContract)

    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useContract('1'), { wrapper })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGetContract).toHaveBeenCalledWith('1', undefined)
    expect(result.current.data).toEqual(mockContract)
  })

  it('should be disabled when id is empty', () => {
    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useContract(''), { wrapper })

    expect(result.current.isFetching).toBe(false)
  })
})

