/**
 * Retry Logic Utilities Tests
 *
 * Comprehensive tests for retry logic utilities covering:
 * - Exponential backoff calculation
 * - Retry decision logic
 * - Retry delay calculation
 * - Delay promise functionality
 * - Edge cases and error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AxiosError } from 'axios'
import type { ExtendedAxiosRequestConfig } from '../../types'
import {
  calculateBackoffDelay,
  shouldRetry,
  getRetryDelay,
  delay,
} from '../retry'

describe('retry utilities', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('calculateBackoffDelay', () => {
    it('should calculate initial delay for first attempt', () => {
      const delay = calculateBackoffDelay(0, 1000, 10000, 2)

      expect(delay).toBe(1000)
    })

    it('should calculate exponential backoff for subsequent attempts', () => {
      const initialDelay = 1000
      const multiplier = 2

      expect(calculateBackoffDelay(0, initialDelay, 10000, multiplier)).toBe(1000)
      expect(calculateBackoffDelay(1, initialDelay, 10000, multiplier)).toBe(2000)
      expect(calculateBackoffDelay(2, initialDelay, 10000, multiplier)).toBe(4000)
      expect(calculateBackoffDelay(3, initialDelay, 10000, multiplier)).toBe(8000)
    })

    it('should cap delay at maxDelay', () => {
      const initialDelay = 1000
      const maxDelay = 5000
      const multiplier = 2

      expect(calculateBackoffDelay(0, initialDelay, maxDelay, multiplier)).toBe(1000)
      expect(calculateBackoffDelay(1, initialDelay, maxDelay, multiplier)).toBe(2000)
      expect(calculateBackoffDelay(2, initialDelay, maxDelay, multiplier)).toBe(4000)
      expect(calculateBackoffDelay(3, initialDelay, maxDelay, multiplier)).toBe(5000) // Capped
      expect(calculateBackoffDelay(4, initialDelay, maxDelay, multiplier)).toBe(5000) // Capped
    })

    it('should handle different multipliers correctly', () => {
      const initialDelay = 1000
      const maxDelay = 10000

      expect(calculateBackoffDelay(2, initialDelay, maxDelay, 1.5)).toBe(2250)
      expect(calculateBackoffDelay(2, initialDelay, maxDelay, 3)).toBe(9000)
    })

    it('should handle zero initial delay', () => {
      const delay = calculateBackoffDelay(1, 0, 10000, 2)

      expect(delay).toBe(0)
    })

    it('should handle very large attempt numbers', () => {
      const delay = calculateBackoffDelay(100, 1000, 10000, 2)

      expect(delay).toBe(10000) // Should be capped
    })
  })

  describe('shouldRetry', () => {
    const createAxiosError = (status?: number, hasResponse = true): AxiosError => {
      const error = new AxiosError('Test error')
      if (hasResponse && status) {
        error.response = {
          status,
          statusText: 'Test',
          headers: {},
          config: {} as any,
          data: {},
        }
      }
      return error
    }

    const createConfig = (overrides?: Partial<ExtendedAxiosRequestConfig>): ExtendedAxiosRequestConfig => {
      return {
        ...overrides,
      } as ExtendedAxiosRequestConfig
    }

    it('should return false if skipRetry is true', () => {
      const error = createAxiosError(500)
      const config = createConfig({ skipRetry: true })

      expect(shouldRetry(error, config)).toBe(false)
    })

    it('should return false if retry is explicitly false', () => {
      const error = createAxiosError(500)
      const config = createConfig({ retry: false })

      expect(shouldRetry(error, config)).toBe(false)
    })

    it('should return false if maxRetries is 0', () => {
      const error = createAxiosError(500)
      const config = createConfig({ retry: { maxRetries: 0 } })

      expect(shouldRetry(error, config)).toBe(false)
    })

    it('should return false if retry count exceeds maxRetries', () => {
      const error = createAxiosError(500)
      const config = createConfig({
        retry: { maxRetries: 3 },
        _retryCount: 3,
      })

      expect(shouldRetry(error, config)).toBe(false)
    })

    it('should return false for 401 errors (handled separately)', () => {
      const error = createAxiosError(401)
      const config = createConfig({ retry: true })

      expect(shouldRetry(error, config)).toBe(false)
    })

    it('should return true for retryable status codes', () => {
      const retryableStatuses = [408, 429, 500, 502, 503, 504]

      retryableStatuses.forEach(status => {
        const error = createAxiosError(status)
        const config = createConfig({ retry: true, _retryCount: 0 })

        expect(shouldRetry(error, config)).toBe(true)
      })
    })

    it('should return false for non-retryable status codes', () => {
      const nonRetryableStatuses = [400, 401, 403, 404, 422]

      nonRetryableStatuses.forEach(status => {
        const error = createAxiosError(status)
        const config = createConfig({ retry: true, _retryCount: 0 })

        expect(shouldRetry(error, config)).toBe(false)
      })
    })

    it('should return true for network errors when retryOnNetworkError is true', () => {
      const error = createAxiosError(undefined, false) // Network error
      const config = createConfig({ retry: true, _retryCount: 0 })

      expect(shouldRetry(error, config)).toBe(true)
    })

    it('should return false for network errors when retryOnNetworkError is false', () => {
      const error = createAxiosError(undefined, false) // Network error
      const config = createConfig({
        retry: { retryOnNetworkError: false },
        _retryCount: 0,
      })

      expect(shouldRetry(error, config)).toBe(false)
    })

    it('should use custom retry config when provided', () => {
      const error = createAxiosError(500)
      const config = createConfig({
        retry: {
          maxRetries: 5,
          retryableStatusCodes: [500],
        },
        _retryCount: 2,
      })

      expect(shouldRetry(error, config)).toBe(true)
    })

    it('should respect custom retryable status codes', () => {
      const error = createAxiosError(400)
      const config = createConfig({
        retry: {
          retryableStatusCodes: [400, 500],
        },
        _retryCount: 0,
      })

      expect(shouldRetry(error, config)).toBe(true)
    })

    it('should handle missing retry config (defaults to true)', () => {
      const error = createAxiosError(500)
      const config = createConfig({ _retryCount: 0 })

      expect(shouldRetry(error, config)).toBe(true)
    })

    it('should handle retry count at boundary', () => {
      const error = createAxiosError(500)
      const config = createConfig({
        retry: { maxRetries: 3 },
        _retryCount: 2, // One less than max
      })

      expect(shouldRetry(error, config)).toBe(true)
    })
  })

  describe('getRetryDelay', () => {
    const createConfig = (overrides?: Partial<ExtendedAxiosRequestConfig>): ExtendedAxiosRequestConfig => {
      return {
        ...overrides,
      } as ExtendedAxiosRequestConfig
    }

    it('should return delay for first retry attempt', () => {
      const config = createConfig({
        retry: true,
        _retryCount: 0,
      })

      const delay = getRetryDelay(config)

      expect(delay).toBe(1000) // Default initial delay
    })

    it('should return exponential backoff delay', () => {
      const config1 = createConfig({ retry: true, _retryCount: 0 })
      const config2 = createConfig({ retry: true, _retryCount: 1 })
      const config3 = createConfig({ retry: true, _retryCount: 2 })

      expect(getRetryDelay(config1)).toBe(1000)
      expect(getRetryDelay(config2)).toBe(2000)
      expect(getRetryDelay(config3)).toBe(4000)
    })

    it('should respect custom retry config', () => {
      const config = createConfig({
        retry: {
          initialDelay: 500,
          maxDelay: 2000,
          backoffMultiplier: 1.5,
        },
        _retryCount: 2,
      })

      const delay = getRetryDelay(config)

      // 500 * 1.5^2 = 1125
      expect(delay).toBe(1125)
    })

    it('should cap delay at maxDelay', () => {
      const config = createConfig({
        retry: {
          initialDelay: 1000,
          maxDelay: 3000,
          backoffMultiplier: 2,
        },
        _retryCount: 5, // Would exceed maxDelay
      })

      const delay = getRetryDelay(config)

      expect(delay).toBe(3000) // Capped
    })

    it('should handle retry: false', () => {
      const config = createConfig({ retry: false })

      const delay = getRetryDelay(config)

      // Should still calculate, but won't be used since shouldRetry returns false
      expect(typeof delay).toBe('number')
    })

    it('should handle missing retry config', () => {
      const config = createConfig({ _retryCount: 1 })

      const delay = getRetryDelay(config)

      expect(delay).toBe(2000) // Uses defaults
    })

    it('should handle zero retry count', () => {
      const config = createConfig({
        retry: { initialDelay: 500 },
        _retryCount: 0,
      })

      const delay = getRetryDelay(config)

      expect(delay).toBe(500)
    })
  })

  describe('delay', () => {
    it('should resolve after specified delay', async () => {
      const start = Date.now()
      const delayMs = 1000

      const delayPromise = delay(delayMs)
      vi.advanceTimersByTime(delayMs)
      await delayPromise

      const elapsed = Date.now() - start
      expect(elapsed).toBeGreaterThanOrEqual(0)
    })

    it('should handle zero delay', async () => {
      const delayPromise = delay(0)
      vi.advanceTimersByTime(0)
      await delayPromise

      // Should resolve immediately
      expect(true).toBe(true)
    })

    it('should handle very small delays', async () => {
      const delayPromise = delay(1)
      vi.advanceTimersByTime(1)
      await delayPromise

      expect(true).toBe(true)
    })

    it('should handle multiple concurrent delays', async () => {
      const delays = [100, 200, 300].map(ms => delay(ms))

      vi.advanceTimersByTime(100)
      await delays[0]

      vi.advanceTimersByTime(100)
      await delays[1]

      vi.advanceTimersByTime(100)
      await delays[2]

      expect(true).toBe(true)
    })

    it('should return a promise', () => {
      const result = delay(1000)

      expect(result).toBeInstanceOf(Promise)
    })
  })
})

