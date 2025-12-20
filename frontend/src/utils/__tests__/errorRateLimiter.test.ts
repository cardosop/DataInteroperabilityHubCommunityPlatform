/**
 * Error Rate Limiter Tests
 *
 * Comprehensive tests for error rate limiting covering:
 * - Error key generation
 * - Rate limiting logic
 * - Time window expiration
 * - Cleanup functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ErrorRateLimiter } from '../errorRateLimiter'

describe('ErrorRateLimiter', () => {
  let limiter: ErrorRateLimiter

  beforeEach(() => {
    limiter = new ErrorRateLimiter(5, 1000) // 5 errors per 1 second
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('should allow first error', () => {
    const error = new Error('Test error')
    expect(limiter.shouldReport(error)).toBe(true)
  })

  it('should allow errors up to max limit', () => {
    const error = new Error('Test error')

    for (let i = 0; i < 5; i++) {
      expect(limiter.shouldReport(error)).toBe(true)
    }
  })

  it('should block errors after max limit', () => {
    const error = new Error('Test error')

    // Report max errors
    for (let i = 0; i < 5; i++) {
      limiter.shouldReport(error)
    }

    // Next error should be blocked
    expect(limiter.shouldReport(error)).toBe(false)
  })

  it('should reset after time window expires', () => {
    const error = new Error('Test error')

    // Report max errors
    for (let i = 0; i < 5; i++) {
      limiter.shouldReport(error)
    }

    // Blocked
    expect(limiter.shouldReport(error)).toBe(false)

    // Advance time past window
    vi.advanceTimersByTime(1001)

    // Should be allowed again
    expect(limiter.shouldReport(error)).toBe(true)
  })

  it('should generate different keys for different errors', () => {
    const error1 = new Error('Error 1')
    const error2 = new Error('Error 2')

    // Both should be allowed
    expect(limiter.shouldReport(error1)).toBe(true)
    expect(limiter.shouldReport(error2)).toBe(true)
  })

  it('should track errors independently', () => {
    const error1 = new Error('Error 1')
    const error2 = new Error('Error 2')

    // Report error1 to limit
    for (let i = 0; i < 5; i++) {
      limiter.shouldReport(error1)
    }

    // error1 should be blocked
    expect(limiter.shouldReport(error1)).toBe(false)

    // error2 should still be allowed
    expect(limiter.shouldReport(error2)).toBe(true)
  })

  it('should reset all entries', () => {
    const error = new Error('Test error')

    // Report to limit
    for (let i = 0; i < 5; i++) {
      limiter.shouldReport(error)
    }

    // Blocked
    expect(limiter.shouldReport(error)).toBe(false)

    // Reset
    limiter.reset()

    // Should be allowed again
    expect(limiter.shouldReport(error)).toBe(true)
  })

  it('should return error counts', () => {
    const error1 = new Error('Error 1')
    const error2 = new Error('Error 2')

    limiter.shouldReport(error1)
    limiter.shouldReport(error1)
    limiter.shouldReport(error2)

    const counts = limiter.getErrorCounts()

    expect(counts.size).toBeGreaterThan(0)
  })
})

