/**
 * Error Testing Utilities
 *
 * Utilities for testing API error handling in E2E tests.
 * Provides helpers to trigger real API errors without mocks/stubs.
 *
 * Uses real API calls - no mocks/stubs. Always fixes root cause.
 */

import { Page, APIRequestContext } from '@playwright/test'
import { apiPost, apiGet, apiPatch, apiDelete, getApiBaseUrl } from './api'

/**
 * Trigger a 400 Bad Request error
 *
 * @param apiContext - API request context
 * @param endpoint - API endpoint to call
 * @param invalidData - Invalid data to send
 * @returns Error response
 */
export async function trigger400Error(
  apiContext: APIRequestContext,
  endpoint: string,
  invalidData: any = {}
): Promise<{ status: number; data: any }> {
  const response = await apiPost(apiContext, endpoint, invalidData)
  // Return response (may be 400 or 201/200 if validation is lenient)
  return { status: response.status, data: response.data }
}

/**
 * Trigger a 401 Unauthorized error
 *
 * @param page - Playwright page (to clear auth tokens)
 * @param apiContext - API request context
 * @param endpoint - API endpoint to call
 * @returns Error response
 */
export async function trigger401Error(
  page: Page,
  apiContext: APIRequestContext,
  endpoint: string
): Promise<{ status: number; data: any }> {
  // Clear authentication tokens
  await page.evaluate(() => {
    localStorage.removeItem('auth_access_token')
    localStorage.removeItem('auth_refresh_token')
    sessionStorage.clear()
  })

  // Wait a bit for tokens to be cleared
  await page.waitForTimeout(500)

  const response = await apiGet(apiContext, endpoint)
  return { status: response.status, data: response.data }
}

/**
 * Trigger a 403 Forbidden error
 *
 * @param apiContext - API request context
 * @param endpoint - API endpoint to call (should require permissions user doesn't have)
 * @returns Error response
 */
export async function trigger403Error(
  apiContext: APIRequestContext,
  endpoint: string
): Promise<{ status: number; data: any }> {
  // Try to access an endpoint that requires admin permissions
  const response = await apiGet(apiContext, endpoint)
  return { status: response.status, data: response.data }
}

/**
 * Trigger a 404 Not Found error
 *
 * @param apiContext - API request context
 * @param resourceType - Type of resource (assets, contracts, etc.)
 * @returns Error response
 */
export async function trigger404Error(
  apiContext: APIRequestContext,
  resourceType: 'assets' | 'contracts' | 'datasets' | 'jobs' | 'users' = 'assets'
): Promise<{ status: number; data: any }> {
  // Use a non-existent UUID
  const fakeId = '00000000-0000-0000-0000-000000000000'
  const endpoint = `/api/v1/${resourceType}/${fakeId}/`

  const response = await apiGet(apiContext, endpoint)
  return { status: response.status, data: response.data }
}

/**
 * Trigger a 429 Rate Limit error
 *
 * @param apiContext - API request context
 * @param endpoint - API endpoint to call
 * @param count - Number of rapid requests to make
 * @returns Error response
 */
export async function trigger429Error(
  apiContext: APIRequestContext,
  endpoint: string,
  count: number = 100
): Promise<{ status: number; data: any; retryAfter?: string }> {
  // Make rapid requests to trigger rate limiting
  const requests = Array.from({ length: count }, () => apiGet(apiContext, endpoint))

  const responses = await Promise.allSettled(requests)

  // Find the first 429 response
  for (const result of responses) {
    if (result.status === 'fulfilled') {
      const response = result.value
      if (response.status === 429) {
        return {
          status: 429,
          data: response.data,
          retryAfter: response.headers?.['retry-after'],
        }
      }
    }
  }

  // If no 429 found, return the last response
  const lastResult = responses[responses.length - 1]
  if (lastResult.status === 'fulfilled') {
    return {
      status: lastResult.value.status,
      data: lastResult.value.data,
      retryAfter: lastResult.value.headers?.['retry-after'],
    }
  }

  // If all requests failed, return a default response
  return { status: 200, data: null }
}

/**
 * Trigger a 500 Server Error
 *
 * Note: This is difficult to trigger reliably without server-side support.
 * We'll try to trigger it by making a request that might cause a server error,
 * or test error handling when it naturally occurs.
 *
 * @param apiContext - API request context
 * @param endpoint - API endpoint to call
 * @returns Error response or null if cannot trigger
 */
export async function trigger500Error(
  apiContext: APIRequestContext,
  endpoint: string
): Promise<{ status: number; data: any } | null> {
  // Try to trigger server error with malformed data
  const response = await apiPost(apiContext, endpoint, {
    // Send data that might cause server error
    _trigger_error: true,
    invalid_nested: { deeply: { nested: { data: null } } },
  })

  if (response.status >= 500) {
    return { status: response.status, data: response.data }
  }

  // If we can't trigger 500, return null
  return null
}

/**
 * Wait for error toast notification to appear
 *
 * @param page - Playwright page
 * @param timeout - Timeout in milliseconds
 * @returns True if error toast appeared
 */
export async function waitForErrorToast(
  page: Page,
  timeout: number = 10000
): Promise<boolean> {
  try {
    await page.waitForSelector(
      '[role="alert"]:has-text("error"), [role="status"]:has-text("error"), .MuiAlert-root[severity="error"]',
      { timeout, state: 'visible' }
    )
    return true
  } catch {
    return false
  }
}

/**
 * Wait for error alert banner to appear
 *
 * @param page - Playwright page
 * @param timeout - Timeout in milliseconds
 * @returns True if error alert appeared
 */
export async function waitForErrorAlert(
  page: Page,
  timeout: number = 10000
): Promise<boolean> {
  try {
    await page.waitForSelector(
      '[role="alert"]:has-text("error"), .MuiAlert-root[severity="error"]',
      { timeout, state: 'visible' }
    )
    return true
  } catch {
    return false
  }
}

/**
 * Wait for error dialog to appear
 *
 * @param page - Playwright page
 * @param timeout - Timeout in milliseconds
 * @returns True if error dialog appeared
 */
export async function waitForErrorDialog(
  page: Page,
  timeout: number = 10000
): Promise<boolean> {
  try {
    await page.waitForSelector(
      '[role="dialog"]:has-text("error"), [role="dialog"]:has-text("Error")',
      { timeout, state: 'visible' }
    )
    return true
  } catch {
    return false
  }
}

/**
 * Get error message text from page
 *
 * @param page - Playwright page
 * @returns Error message text or null
 */
export async function getErrorMessage(page: Page): Promise<string | null> {
  const errorSelectors = [
    '[role="alert"]',
    '[role="status"]',
    '.MuiAlert-root',
    'text=/error/i',
    'text=/failed/i',
  ]

  for (const selector of errorSelectors) {
    const element = page.locator(selector).first()
    if (await element.isVisible().catch(() => false)) {
      const text = await element.textContent()
      if (text && text.trim().length > 0) {
        return text.trim()
      }
    }
  }

  return null
}

/**
 * Check if page redirected to login (401 handling)
 *
 * @param page - Playwright page
 * @returns True if redirected to login
 */
export async function isRedirectedToLogin(page: Page): Promise<boolean> {
  await page.waitForTimeout(1000) // Wait for potential redirect
  const url = page.url()
  return url.includes('/login') || url.includes('/auth/login')
}

/**
 * Check if retry button is visible
 *
 * @param page - Playwright page
 * @returns True if retry button is visible
 */
export async function hasRetryButton(page: Page): Promise<boolean> {
  const retryButton = page.locator('button:has-text("Retry"), button:has-text("Try Again")').first()
  return await retryButton.isVisible().catch(() => false)
}

/**
 * Click retry button
 *
 * @param page - Playwright page
 */
export async function clickRetryButton(page: Page): Promise<void> {
  const retryButton = page.locator('button:has-text("Retry"), button:has-text("Try Again")').first()
  await retryButton.waitFor({ state: 'visible', timeout: 10000 })
  await retryButton.click()
  await page.waitForTimeout(1000) // Wait for retry action
}

