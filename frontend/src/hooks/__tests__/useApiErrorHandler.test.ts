/**
 * useApiErrorHandler Tests
 *
 * Comprehensive tests for the useApiErrorHandler hook.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useApiErrorHandler, ErrorCode } from '../useApiErrorHandler'
import { ValidationException, ServerException, RateLimitException } from '@/lib/api/exceptions'
import { NetworkError } from '@/lib/api/errors'
import { FetchError } from '@/lib/api/fetch'

// Mock useToastManager
const mockShowToast = vi.fn()
vi.mock('@/components/feedback/Toast/useToastManager', () => ({
  useToastManager: () => ({
    showToast: mockShowToast,
  }),
}))

const createTestQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient()
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useApiErrorHandler', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Error Code Mapping', () => {
    it('should map validation error to VALIDATION_ERROR code', () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ValidationException('Validation failed')

      const mappedCode = result.current.mapErrorToCode(error)
      expect(mappedCode).toBe(ErrorCode.VALIDATION_ERROR)
    })

    it('should map server error to SERVER_ERROR code', () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ServerException('Server error', 500)

      const mappedCode = result.current.mapErrorToCode(error)
      expect(mappedCode).toBe(ErrorCode.SERVER_ERROR)
    })

    it('should map network error to NETWORK_ERROR code', () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const fetchError = new FetchError('Network error')
      const error = new NetworkError('Network error', fetchError)

      const mappedCode = result.current.mapErrorToCode(error)
      expect(mappedCode).toBe(ErrorCode.NETWORK_ERROR)
    })

    it('should map rate limit error to RATE_LIMIT_EXCEEDED code', () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new RateLimitException('Rate limit exceeded', 60)

      const mappedCode = result.current.mapErrorToCode(error)
      expect(mappedCode).toBe(ErrorCode.RATE_LIMIT_EXCEEDED)
    })
  })

  describe('Error Handling', () => {
    it('should handle error and show toast notification', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ValidationException('Validation failed')

      await result.current.handleError(error)

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalledWith({
          message: expect.stringContaining('check your input'),
          severity: 'warning',
        })
      })
    })

    it('should handle error without toast when showToast is false', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ValidationException('Validation failed')

      await result.current.handleError(error, { showToast: false })

      expect(mockAddToast).not.toHaveBeenCalled()
    })

    it('should use custom error message when provided', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ValidationException('Validation failed')

      await result.current.handleError(error, {
        customMessage: 'Custom error message',
      })

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalledWith({
          message: 'Custom error message',
          severity: 'warning',
        })
      })
    })
  })

  describe('Error Recovery', () => {
    it('should preserve error context when preserveContext is true', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ServerException('Server error', 500)

      await result.current.handleError(error, {
        preserveContext: true,
        context: { userId: 'user-1' },
      })

      const context = result.current.getErrorContext()
      expect(context).not.toBeNull()
      expect(context?.context?.userId).toBe('user-1')
    })

    it('should clear error context', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ServerException('Server error', 500)

      await result.current.handleError(error, {
        preserveContext: true,
      })

      result.current.clearErrorContext()
      const context = result.current.getErrorContext()
      expect(context).toBeNull()
    })

    it('should retry with context preservation', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ServerException('Server error', 500)
      const retryFn = vi.fn().mockResolvedValue(undefined)

      await result.current.handleError(error, {
        preserveContext: true,
      })

      await result.current.retryWithContext(retryFn)

      expect(retryFn).toHaveBeenCalled()
      const context = result.current.getErrorContext()
      expect(context?.retryCount).toBe(1)
    })
  })

  describe('Specific Error Handlers', () => {
    it('should handle validation error with handleValidationError', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ValidationException('Validation failed')

      await result.current.handleValidationError(error)

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalled()
      })
    })

    it('should handle server error with handleServerError', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const error = new ServerException('Server error', 500)

      await result.current.handleServerError(error)

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalled()
      })
    })

    it('should handle network error with handleNetworkError', async () => {
      const { result } = renderHook(() => useApiErrorHandler(), { wrapper })
      const fetchError = new FetchError('Network error')
      const error = new NetworkError('Network error', fetchError)

      await result.current.handleNetworkError(error)

      await waitFor(() => {
        expect(mockAddToast).toHaveBeenCalled()
      })
    })
  })
})

