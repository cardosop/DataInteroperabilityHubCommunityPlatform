/**
 * useComplianceScans Hook Tests
 *
 * Tests for the compliance scans list query hook.
 * These tests verify hook structure and query behavior.
 *
 * Note: These tests verify the hook's structure and behavior.
 * Full integration tests with a running backend are required for complete coverage.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useComplianceScans } from '../useComplianceScans'
import { createHookWrapper } from './test-utils'
import * as complianceApi from '@/lib/api/compliance'

// Mock the compliance API
vi.mock('@/lib/api/compliance', () => ({
  listComplianceScans: vi.fn(),
}))

describe('useComplianceScans', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct query structure', () => {
    const mockListComplianceScans = vi.mocked(complianceApi.listComplianceScans)
    mockListComplianceScans.mockResolvedValue({
      count: 0,
      page: 1,
      page_size: 50,
      total_pages: 0,
      next: null,
      previous: null,
      results: [],
    })

    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useComplianceScans(), { wrapper })

    expect(result.current).toHaveProperty('data')
    expect(result.current).toHaveProperty('isLoading')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('refetch')
  })

  it('should call listComplianceScans with params', async () => {
    const mockListComplianceScans = vi.mocked(complianceApi.listComplianceScans)
    mockListComplianceScans.mockResolvedValue({
      count: 2,
      page: 1,
      page_size: 20,
      total_pages: 1,
      next: null,
      previous: null,
      results: [
        {
          id: '1',
          tenant: 'tenant-1',
          job: 'job-1',
          status: 'SUCCEEDED',
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
        },
        {
          id: '2',
          tenant: 'tenant-1',
          job: 'job-2',
          status: 'RUNNING',
          created_at: '2025-01-01T00:00:00Z',
          updated_at: '2025-01-01T00:00:00Z',
        },
      ],
    })

    const wrapper = createHookWrapper()
    const params = { page: 1, page_size: 20, ordering: '-created_at', status: 'SUCCEEDED' as const }
    const { result } = renderHook(() => useComplianceScans(params), { wrapper })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockListComplianceScans).toHaveBeenCalledWith(params, undefined)
    expect(result.current.data?.results).toHaveLength(2)
  })

  it('should handle query options', () => {
    const mockListComplianceScans = vi.mocked(complianceApi.listComplianceScans)
    mockListComplianceScans.mockResolvedValue({
      count: 0,
      page: 1,
      page_size: 50,
      total_pages: 0,
      next: null,
      previous: null,
      results: [],
    })

    const wrapper = createHookWrapper()
    const { result } = renderHook(
      () => useComplianceScans(undefined, { enabled: false, staleTime: 10000 }),
      { wrapper }
    )

    expect(result.current).toBeDefined()
  })
})

