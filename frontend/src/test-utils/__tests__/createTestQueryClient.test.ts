/**
 * createTestQueryClient Tests
 *
 * Tests for the createTestQueryClient utility.
 */

import { describe, it, expect } from 'vitest'
import {
  createTestQueryClient,
  createTestQueryClientWithCache,
} from '../createTestQueryClient'

describe('createTestQueryClient', () => {
  it('should create a QueryClient with test-friendly defaults', () => {
    const queryClient = createTestQueryClient()
    expect(queryClient).toBeDefined()
  })

  it('should disable retries by default', () => {
    const queryClient = createTestQueryClient()
    const defaultOptions = queryClient.getDefaultOptions()
    expect(defaultOptions.queries?.retry).toBe(false)
    expect(defaultOptions.mutations?.retry).toBe(false)
  })

  it('should disable caching by default', () => {
    const queryClient = createTestQueryClient()
    const defaultOptions = queryClient.getDefaultOptions()
    expect(defaultOptions.queries?.gcTime).toBe(0)
    expect(defaultOptions.queries?.staleTime).toBe(0)
  })

  it('should use custom options when provided', () => {
    const queryClient = createTestQueryClient({
      retry: true,
      gcTime: 1000,
      staleTime: 500,
    })
    const defaultOptions = queryClient.getDefaultOptions()
    expect(defaultOptions.queries?.retry).toBe(true)
    expect(defaultOptions.queries?.gcTime).toBe(1000)
    expect(defaultOptions.queries?.staleTime).toBe(500)
  })

  it('should create QueryClient with cache when using createTestQueryClientWithCache', () => {
    const queryClient = createTestQueryClientWithCache()
    const defaultOptions = queryClient.getDefaultOptions()
    expect(defaultOptions.queries?.gcTime).toBe(5 * 60 * 1000) // 5 minutes
  })
})

