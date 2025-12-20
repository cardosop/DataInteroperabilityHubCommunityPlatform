/**
 * Password Reset Helpers for Playwright Tests
 *
 * Utilities for password reset flow testing.
 * Provides helpers for requesting password reset and getting reset tokens.
 *
 * Uses real API calls - no mocks/stubs. Always fixes root cause.
 */

import { Page, APIRequestContext } from '@playwright/test'
import { apiPost, getApiBaseUrl } from './api'

/**
 * Password reset request response
 */
export interface PasswordResetRequestResponse {
  message: string
}

/**
 * Password reset confirm request
 */
export interface PasswordResetConfirmRequest {
  token: string
  new_password: string
}

/**
 * Password reset confirm response
 */
export interface PasswordResetConfirmResponse {
  message: string
}

/**
 * Request password reset via API
 *
 * @param context - API request context or page
 * @param email - User email address
 * @returns Password reset request response
 *
 * @example
 * ```ts
 * const response = await requestPasswordReset(page, 'user@example.com')
 * ```
 */
export async function requestPasswordReset(
  context: Page | APIRequestContext,
  email: string
): Promise<PasswordResetRequestResponse> {
  const apiBaseUrl = getApiBaseUrl()
  const response = await apiPost<PasswordResetRequestResponse>(
    context,
    `${apiBaseUrl}/api/v1/auth/password-reset/`,
    { email },
    {
      headers: {
        'Content-Type': 'application/json',
      },
    }
  )

  if (response.status !== 200) {
    throw new Error(
      `Password reset request failed: ${response.status} ${response.statusText}. ${JSON.stringify(response.data)}`
    )
  }

  return response.data
}

/**
 * Confirm password reset via API
 *
 * @param context - API request context or page
 * @param token - Password reset token
 * @param newPassword - New password
 * @returns Password reset confirm response
 *
 * @example
 * ```ts
 * const response = await confirmPasswordReset(page, token, 'NewPassword123')
 * ```
 */
export async function confirmPasswordReset(
  context: Page | APIRequestContext,
  token: string,
  newPassword: string
): Promise<PasswordResetConfirmResponse> {
  const apiBaseUrl = getApiBaseUrl()
  const response = await apiPost<PasswordResetConfirmResponse>(
    context,
    `${apiBaseUrl}/api/v1/auth/password-reset/confirm/`,
    {
      token,
      new_password: newPassword,
    } as PasswordResetConfirmRequest,
    {
      headers: {
        'Content-Type': 'application/json',
      },
    }
  )

  if (response.status !== 200) {
    const errorData = response.data as any
    throw new Error(
      `Password reset confirm failed: ${response.status} ${response.statusText}. ${JSON.stringify(errorData)}`
    )
  }

  return response.data
}

/**
 * Get password reset token for a user
 *
 * This function attempts to get the password reset token from the backend.
 * Since we can't access the database directly from frontend E2E tests,
 * this function uses a test API endpoint or direct database query helper.
 *
 * Note: This requires a test helper endpoint or direct database access.
 * If neither is available, the token must be obtained through other means
 * (e.g., email service in test mode, or a test-specific API endpoint).
 *
 * @param context - API request context or page
 * @param email - User email address
 * @returns Password reset token or null if not found
 *
 * @example
 * ```ts
 * const token = await getPasswordResetToken(page, 'user@example.com')
 * if (token) {
 *   await confirmPasswordReset(page, token, 'NewPassword123')
 * }
 * ```
 */
export async function getPasswordResetToken(
  context: Page | APIRequestContext,
  email: string
): Promise<string | null> {
  const apiBaseUrl = getApiBaseUrl()

  // Try to get token from test API endpoint (if available)
  // This endpoint should only be available in test environments
  try {
    const requestContext = 'request' in context ? context.request : context
    const testEndpoint = `${apiBaseUrl}/api/v1/test/password-reset-token/`

    const response = await requestContext.post(testEndpoint, {
      data: { email },
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (response.ok()) {
      const data = await response.json()
      return data.token || null
    }
  } catch (error) {
    // Test endpoint not available, try alternative methods
    console.warn('[Password Reset] Test endpoint not available, trying alternative method')
  }

  // Alternative: Use a test helper that queries the database directly
  // This would require a test-specific API endpoint or direct database access
  // For now, return null and let the test handle token retrieval differently
  return null
}

/**
 * Request password reset and get token (for testing)
 *
 * This is a convenience function that requests password reset and attempts
 * to get the token. It's useful for E2E tests where you need both operations.
 *
 * @param context - API request context or page
 * @param email - User email address
 * @returns Object with request response and token (if available)
 *
 * @example
 * ```ts
 * const { response, token } = await requestPasswordResetAndGetToken(page, 'user@example.com')
 * if (token) {
 *   await confirmPasswordReset(page, token, 'NewPassword123')
 * }
 * ```
 */
export async function requestPasswordResetAndGetToken(
  context: Page | APIRequestContext,
  email: string
): Promise<{
  response: PasswordResetRequestResponse
  token: string | null
}> {
  // Request password reset
  const response = await requestPasswordReset(context, email)

  // Try to get token
  const token = await getPasswordResetToken(context, email)

  return { response, token }
}

/**
 * Wait for password reset token to be available
 *
 * This function polls for the password reset token to become available.
 * Useful when the token is generated asynchronously.
 *
 * @param context - API request context or page
 * @param email - User email address
 * @param timeout - Maximum time to wait in milliseconds
 * @param interval - Polling interval in milliseconds
 * @returns Password reset token or null if timeout
 *
 * @example
 * ```ts
 * const token = await waitForPasswordResetToken(page, 'user@example.com', 10000, 1000)
 * ```
 */
export async function waitForPasswordResetToken(
  context: Page | APIRequestContext,
  email: string,
  timeout: number = 10000,
  interval: number = 1000
): Promise<string | null> {
  const startTime = Date.now()

  while (Date.now() - startTime < timeout) {
    const token = await getPasswordResetToken(context, email)
    if (token) {
      return token
    }

    await new Promise((resolve) => setTimeout(resolve, interval))
  }

  return null
}

