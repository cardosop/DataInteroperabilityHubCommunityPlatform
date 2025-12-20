/**
 * Error Rate Limiter
 *
 * Utility for preventing error spam by limiting the number of errors
 * that can be reported within a time window.
 */

interface ErrorEntry {
  count: number
  firstOccurrence: number
  lastOccurrence: number
}

/**
 * Error rate limiter class
 */
export class ErrorRateLimiter {
  private errors: Map<string, ErrorEntry> = new Map()
  private readonly maxErrors: number
  private readonly timeWindow: number // in milliseconds

  /**
   * Create a new error rate limiter
   *
   * @param maxErrors - Maximum number of errors allowed in time window
   * @param timeWindow - Time window in milliseconds
   */
  constructor(maxErrors: number = 10, timeWindow: number = 60000) {
    this.maxErrors = maxErrors
    this.timeWindow = timeWindow
  }

  /**
   * Generate a key for an error
   *
   * @param error - Error object
   * @returns Error key
   */
  private getErrorKey(error: unknown): string {
    if (error instanceof Error) {
      // Use error message and stack trace (first line) as key
      const stackLine = error.stack?.split('\n')[1] || ''
      return `${error.name}:${error.message}:${stackLine}`
    }

    if (typeof error === 'string') {
      return `string:${error}`
    }

    if (typeof error === 'object' && error !== null) {
      try {
        // Use a simplified representation
        const keys = Object.keys(error).sort().join(',')
        return `object:${keys}`
      } catch {
        return 'unknown'
      }
    }

    return `primitive:${String(error)}`
  }

  /**
   * Check if error should be reported (not rate limited)
   *
   * @param error - Error to check
   * @returns True if error should be reported
   */
  shouldReport(error: unknown): boolean {
    const key = this.getErrorKey(error)
    const now = Date.now()
    const entry = this.errors.get(key)

    // Clean up old entries
    this.cleanup(now)

    if (!entry) {
      // First occurrence
      this.errors.set(key, {
        count: 1,
        firstOccurrence: now,
        lastOccurrence: now,
      })
      return true
    }

    // Check if within time window
    const timeSinceFirst = now - entry.firstOccurrence

    if (timeSinceFirst > this.timeWindow) {
      // Time window expired, reset
      this.errors.set(key, {
        count: 1,
        firstOccurrence: now,
        lastOccurrence: now,
      })
      return true
    }

    // Check if max errors exceeded
    if (entry.count >= this.maxErrors) {
      // Rate limited
      entry.lastOccurrence = now
      return false
    }

    // Increment count
    entry.count++
    entry.lastOccurrence = now
    return true
  }

  /**
   * Clean up old entries outside the time window
   *
   * @param now - Current timestamp
   */
  private cleanup(now: number): void {
    for (const [key, entry] of this.errors.entries()) {
      const timeSinceLast = now - entry.lastOccurrence
      if (timeSinceLast > this.timeWindow) {
        this.errors.delete(key)
      }
    }
  }

  /**
   * Reset rate limiter (clear all entries)
   */
  reset(): void {
    this.errors.clear()
  }

  /**
   * Get current error counts
   *
   * @returns Map of error keys to counts
   */
  getErrorCounts(): Map<string, number> {
    const counts = new Map<string, number>()
    for (const [key, entry] of this.errors.entries()) {
      counts.set(key, entry.count)
    }
    return counts
  }
}

/**
 * Global error rate limiter instance
 */
export const globalErrorRateLimiter = new ErrorRateLimiter(10, 60000) // 10 errors per minute

