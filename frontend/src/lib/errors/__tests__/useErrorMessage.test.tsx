/**
 * useErrorMessage Hook Tests
 *
 * Comprehensive tests for the useErrorMessage hook covering:
 * - Localized messages
 * - Template retrieval
 * - i18n integration
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useErrorMessage } from '../useErrorMessage'
import { ApiError } from '@/lib/api/errors'
import { FetchError } from '@/lib/api/fetch'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => {
      // Return default value if provided, otherwise return key
      return options?.defaultValue || key
    },
    i18n: {
      language: 'en',
    },
  }),
}))

describe('useErrorMessage', () => {
  describe('Basic Functionality', () => {
    it('should return error message template', () => {
      const axiosError = {
        response: { status: 404 },
      } as FetchError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)
      const { result } = renderHook(() => useErrorMessage(apiError))

      expect(result.current.template).toBeDefined()
      expect(result.current.title).toBeTruthy()
      expect(result.current.message).toBeTruthy()
    })

    it('should return suggested actions', () => {
      const axiosError = {
        response: { status: 403 },
      } as FetchError

      const apiError = new ApiError('Forbidden', 'FORBIDDEN', 403, axiosError)
      const { result } = renderHook(() => useErrorMessage(apiError))

      expect(Array.isArray(result.current.suggestedActions)).toBe(true)
    })

    it('should return help links', () => {
      const axiosError = {
        response: { status: 500 },
      } as FetchError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)
      const { result } = renderHook(() => useErrorMessage(apiError))

      expect(Array.isArray(result.current.helpLinks)).toBe(true)
    })

    it('should return next steps', () => {
      const axiosError = {
        response: { status: 400 },
      } as FetchError

      const apiError = new ApiError('Validation error', 'VALIDATION_ERROR', 400, axiosError)
      const { result } = renderHook(() => useErrorMessage(apiError))

      expect(Array.isArray(result.current.nextSteps)).toBe(true)
      expect(result.current.nextSteps.length).toBeGreaterThan(0)
    })

    it('should return recoverable status', () => {
      const axiosError = {
        response: { status: 500 },
      } as FetchError

      const apiError = new ApiError('Server error', 'INTERNAL_SERVER_ERROR', 500, axiosError)
      const { result } = renderHook(() => useErrorMessage(apiError))

      expect(typeof result.current.recoverable).toBe('boolean')
    })
  })

  describe('i18n Integration', () => {
    it('should use i18n translations when available', () => {
      const mockT = vi.fn((key: string, options?: { defaultValue?: string }) => {
        if (key.includes('errors.notFound.title')) {
          return 'Página No Encontrada' // Spanish translation
        }
        return options?.defaultValue || key
      })

      vi.mocked(require('react-i18next')).useTranslation = () => ({
        t: mockT,
        i18n: { language: 'es' },
      })

      const axiosError = {
        response: { status: 404 },
      } as FetchError

      const apiError = new ApiError('Not found', 'NOT_FOUND', 404, axiosError)
      const { result } = renderHook(() => useErrorMessage(apiError))

      // Should call translation function
      expect(mockT).toHaveBeenCalled()
    })
  })
})

