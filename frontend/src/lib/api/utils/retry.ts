/**
 * Retry Logic Utilities
 *
 * Utilities for implementing retry logic with exponential backoff.
 */

import type { ExtendedFetchRequestInit, RetryConfig } from '../types'
import { FetchError } from '../fetch'

/**
 * Default retry configuration
 */
const DEFAULT_RETRY_CONFIG: Required<RetryConfig> = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffMultiplier: 2,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],
  retryOnNetworkError: true,
}

/**
 * Calculate delay for exponential backoff
 */
export function calculateBackoffDelay(
  attempt: number,
  initialDelay: number,
  maxDelay: number,
  multiplier: number
): number {
  const delay = initialDelay * Math.pow(multiplier, attempt)
  return Math.min(delay, maxDelay)
}

/**
 * Check if an error should be retried
 */
export function shouldRetry(error: FetchError | Error, config: ExtendedFetchRequestInit): boolean {
  // Skip retry if explicitly disabled
  if (config.skipRetry) {
    return false
  }

  // Get retry config
  const retryConfig: RetryConfig =
    config.retry === true
      ? DEFAULT_RETRY_CONFIG
      : config.retry === false
        ? { maxRetries: 0 }
        : { ...DEFAULT_RETRY_CONFIG, ...config.retry }

  if (retryConfig.maxRetries === 0) {
    return false
  }

  // Check retry count
  const retryCount = config._retryCount || 0
  if (retryCount >= retryConfig.maxRetries) {
    return false
  }

  // Check if it's a network error
  const fetchError = error instanceof FetchError ? error : null
  if (!fetchError?.response && retryConfig.retryOnNetworkError) {
    return true
  }

  // Check status code (don't retry 401 - handled separately)
  if (fetchError?.response) {
    // Never retry 401 errors - they're handled by token refresh logic
    if (fetchError.response.status === 401) {
      return false
    }
    return retryConfig.retryableStatusCodes.includes(fetchError.response.status)
  }

  return false
}

/**
 * Get retry delay for a request
 */
export function getRetryDelay(config: ExtendedFetchRequestInit): number {
  const retryConfig: RetryConfig =
    config.retry === true
      ? DEFAULT_RETRY_CONFIG
      : config.retry === false
        ? { maxRetries: 0 }
        : { ...DEFAULT_RETRY_CONFIG, ...config.retry }

  const retryCount = config._retryCount || 0

  // Check for Retry-After header in response (if available in error)
  // This will be handled in the interceptor

  return calculateBackoffDelay(
    retryCount,
    retryConfig.initialDelay,
    retryConfig.maxDelay,
    retryConfig.backoffMultiplier
  )
}

/**
 * Create a promise that resolves after a delay
 */
export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
