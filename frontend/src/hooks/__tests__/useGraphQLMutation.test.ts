/**
 * useGraphQLMutation Hook Tests
 *
 * Tests for the generic GraphQL mutation hook.
 * These tests verify hook structure and mutation behavior.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useGraphQLMutation } from '../useGraphQLMutation'
import { createHookWrapper } from './test-utils'
import * as graphqlApi from '@/lib/api/graphql'
import { gql } from '@apollo/client'

// Mock the GraphQL API
vi.mock('@/lib/api/graphql', () => ({
  executeMutation: vi.fn(),
}))

describe('useGraphQLMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return correct mutation structure', () => {
    const CREATE_ASSET = gql`
      mutation CreateAsset($input: AssetInput!) {
        createAsset(input: $input) {
          asset {
            id
            name
          }
        }
      }
    `

    const wrapper = createHookWrapper()
    const { result } = renderHook(
      () => useGraphQLMutation({ mutation: CREATE_ASSET }),
      { wrapper }
    )

    expect(result.current).toHaveProperty('mutate')
    expect(result.current).toHaveProperty('mutateAsync')
    expect(result.current).toHaveProperty('isPending')
    expect(result.current).toHaveProperty('isError')
    expect(result.current).toHaveProperty('isSuccess')
    expect(result.current).toHaveProperty('error')
    expect(result.current).toHaveProperty('data')
  })

  it('should initially be in idle state', () => {
    const CREATE_ASSET = gql`
      mutation CreateAsset($input: AssetInput!) {
        createAsset(input: $input) {
          asset {
            id
            name
          }
        }
      }
    `

    const wrapper = createHookWrapper()
    const { result } = renderHook(
      () => useGraphQLMutation({ mutation: CREATE_ASSET }),
      { wrapper }
    )

    expect(result.current.isPending).toBe(false)
    expect(result.current.isError).toBe(false)
    expect(result.current.isSuccess).toBe(false)
    expect(result.current.data).toBeUndefined()
    expect(result.current.error).toBeNull()
  })
})

