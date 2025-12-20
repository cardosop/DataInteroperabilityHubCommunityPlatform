/**
 * useGraphQLQuery Hook Tests
 *
 * Tests for the generic GraphQL query hook.
 * These tests verify hook structure and query behavior.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useGraphQLQuery } from '../useGraphQLQuery'
import { createHookWrapper } from './test-utils'
import * as graphqlApi from '@/lib/api/graphql'
import { gql } from '@apollo/client'

// Mock the GraphQL API
vi.mock('@/lib/api/graphql', () => ({
  executeQuery: vi.fn(),
}))

describe('useGraphQLQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct query structure', () => {
    const mockExecuteQuery = vi.mocked(graphqlApi.executeQuery)
    mockExecuteQuery.mockResolvedValue({
      data: { asset: { id: '1', name: 'Test Asset' } },
    })

    const GET_ASSET = gql`
      query GetAsset($id: ID!) {
        asset(id: $id) {
          id
          name
        }
      }
    `

    const wrapper = createHookWrapper()
    const { result } = renderHook(
      () => useGraphQLQuery({ query: GET_ASSET, variables: { id: '1' } }),
      { wrapper }
    )

    expect(result.current).toHaveProperty('data')
    expect(result.current).toHaveProperty('isLoading')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('refetch')
  })

  it('should call executeQuery with correct parameters', async () => {
    const mockExecuteQuery = vi.mocked(graphqlApi.executeQuery)
    mockExecuteQuery.mockResolvedValue({
      data: { asset: { id: '1', name: 'Test Asset' } },
    })

    const GET_ASSET = gql`
      query GetAsset($id: ID!) {
        asset(id: $id) {
          id
          name
        }
      }
    `

    const wrapper = createHookWrapper()
    const { result } = renderHook(
      () =>
        useGraphQLQuery({
          query: GET_ASSET,
          variables: { id: '1' },
          fetchPolicy: 'network-only',
        }),
      { wrapper }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockExecuteQuery).toHaveBeenCalledWith(
      GET_ASSET,
      { id: '1' },
      { fetchPolicy: 'network-only', errorPolicy: undefined }
    )
  })
})

