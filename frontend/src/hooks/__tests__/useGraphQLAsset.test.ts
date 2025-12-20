/**
 * useGraphQLAsset Hook Tests
 *
 * Tests for the example GraphQL asset query hook.
 * These tests verify hook structure and query behavior.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useGraphQLAsset } from '../useGraphQLAsset'
import { createHookWrapper } from './test-utils'
import * as graphqlHooks from '../useGraphQLQuery'

// Mock the GraphQL query hook
vi.mock('../useGraphQLQuery', () => ({
  useGraphQLQuery: vi.fn(),
}))

describe('useGraphQLAsset', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct query structure', () => {
    const mockUseGraphQLQuery = vi.mocked(graphqlHooks.useGraphQLQuery)
    mockUseGraphQLQuery.mockReturnValue({
      data: { asset: { id: '1', name: 'Test Asset' } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const wrapper = createHookWrapper()
    const { result } = renderHook(() => useGraphQLAsset('1'), { wrapper })

    expect(result.current).toHaveProperty('data')
    expect(result.current).toHaveProperty('isLoading')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('error')
  })

  it('should call useGraphQLQuery with correct parameters', () => {
    const mockUseGraphQLQuery = vi.mocked(graphqlHooks.useGraphQLQuery)
    mockUseGraphQLQuery.mockReturnValue({
      data: { asset: { id: '1', name: 'Test Asset' } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const wrapper = createHookWrapper()
    renderHook(() => useGraphQLAsset('1'), { wrapper })

    expect(mockUseGraphQLQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.any(Object),
        variables: { id: '1' },
      })
    )
  })

  it('should be disabled when id is empty', () => {
    const mockUseGraphQLQuery = vi.mocked(graphqlHooks.useGraphQLQuery)
    mockUseGraphQLQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    const wrapper = createHookWrapper()
    renderHook(() => useGraphQLAsset(''), { wrapper })

    expect(mockUseGraphQLQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryOptions: expect.objectContaining({
          enabled: false,
        }),
      })
    )
  })
})

