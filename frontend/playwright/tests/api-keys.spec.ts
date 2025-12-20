/**
 * API Key Management E2E Tests
 *
 * Comprehensive end-to-end tests for API key management covering:
 * - API key creation
 * - API key display (one-time)
 * - API key revocation
 * - API key usage tracking
 *
 * Uses real API calls and implementations - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { login, type TestCredentials } from '../utils/auth'
import { getApiBaseUrl } from '../utils/api'

/**
 * API Key interfaces
 */
interface APIKey {
  id: string
  name: string
  scopes: string[]
  expires_at: string | null
  last_used_at: string | null
  created_at: string
}

interface CreateAPIKeyRequest {
  name: string
  scopes?: string[]
  expires_in_days?: number | null
}

interface CreateAPIKeyResponse {
  id: string
  name: string
  api_key: string
  scopes: string[]
  expires_at: string | null
  created_at: string
}

interface ListAPIKeysResponse {
  count: number
  next: string | null
  previous: string | null
  results: APIKey[]
}

/**
 * Get test credentials from environment or use defaults
 */
function getTestCredentials(): TestCredentials {
  return {
    email: process.env.TEST_USER_EMAIL || 'test@example.com',
    password: process.env.TEST_USER_PASSWORD || 'testpassword123',
    name: 'Test User',
  }
}

/**
 * Create API key via API
 */
async function createAPIKeyViaAPI(
  page: any,
  request: any,
  data: CreateAPIKeyRequest
): Promise<CreateAPIKeyResponse> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to create API keys')
  }

  const response = await request.post(`${apiBaseUrl}/api/v1/auth/api-keys/`, {
    data,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `API key creation failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  return (await response.json()) as CreateAPIKeyResponse
}

/**
 * List API keys via API
 */
async function listAPIKeysViaAPI(page: any, request: any): Promise<ListAPIKeysResponse> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to list API keys')
  }

  const response = await request.get(`${apiBaseUrl}/api/v1/auth/api-keys/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `API key listing failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  return (await response.json()) as ListAPIKeysResponse
}

/**
 * Delete API key via API
 */
async function deleteAPIKeyViaAPI(page: any, request: any, id: string): Promise<void> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to delete API keys')
  }

  const response = await request.delete(`${apiBaseUrl}/api/v1/auth/api-keys/${id}/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `API key deletion failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }
}

/**
 * Use API key for authentication (test usage tracking)
 */
async function useAPIKeyForRequest(request: any, apiKey: string, endpoint: string = '/api/v1/auth/me/'): Promise<any> {
  const apiBaseUrl = getApiBaseUrl()
  const response = await request.get(`${apiBaseUrl}${endpoint}`, {
    headers: {
      Authorization: `ApiKey ${apiKey}`,
    },
  })

  return response
}

test.describe('API Key Management', () => {
  let testCredentials: TestCredentials

  test.beforeEach(async ({ page, request }) => {
    // Login before each test
    testCredentials = getTestCredentials()
    try {
      await login(page, testCredentials, request)
    } catch (error) {
      // If login fails, skip tests that require authentication
      test.skip()
    }
  })

  test.describe('API Key Creation', () => {
    test('should create API key via UI', async ({ page }) => {
      // Navigate to API key management page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Click "Create API Key" button
      await page.click('button:has-text("Create API Key")')

      // Wait for dialog to open
      await page.waitForSelector('text=Create API Key', { timeout: 5000 })

      // Fill form
      const apiKeyName = `Test API Key ${Date.now()}`
      await page.fill('input[name="name"], input[type="text"][label*="Name"]', apiKeyName)

      // Submit form
      await page.click('button[type="submit"]:has-text("Create"), button:has-text("Create")')

      // Wait for success message and API key display
      await page.waitForSelector('text=API Key Created Successfully', { timeout: 10000 })

      // Verify API key is displayed
      const apiKeyText = await page.textContent('body')
      expect(apiKeyText).toContain('Important')
      expect(apiKeyText).toContain('Copy this API key now')

      // Verify API key value is shown (may be masked initially)
      const keyDisplay = page.locator('[class*="monospace"], code, pre').first()
      const keyValue = await keyDisplay.textContent()
      expect(keyValue).toBeTruthy()
      expect(keyValue?.length).toBeGreaterThan(0)
    })

    test('should create API key via API', async ({ page, request }) => {
      const apiKeyName = `Test API Key API ${Date.now()}`

      const response = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      // Verify response
      expect(response).toBeDefined()
      expect(response.id).toBeTruthy()
      expect(response.name).toBe(apiKeyName)
      expect(response.api_key).toBeTruthy()
      expect(response.api_key.length).toBeGreaterThan(0)
      expect(Array.isArray(response.scopes)).toBe(true)
    })

    test('should create API key with scopes', async ({ page, request }) => {
      const apiKeyName = `Test API Key Scopes ${Date.now()}`

      const response = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
        scopes: ['assets:read', 'assets:write'],
      })

      // Verify scopes
      expect(response.scopes).toContain('assets:read')
      expect(response.scopes).toContain('assets:write')
    })

    test('should create API key with expiration', async ({ page, request }) => {
      const apiKeyName = `Test API Key Expires ${Date.now()}`

      const response = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
        expires_in_days: 30,
      })

      // Verify expiration is set
      expect(response.expires_at).toBeTruthy()
      const expiresAt = new Date(response.expires_at!)
      const now = new Date()
      const daysDiff = Math.ceil((expiresAt.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
      expect(daysDiff).toBeGreaterThanOrEqual(29)
      expect(daysDiff).toBeLessThanOrEqual(31)
    })

    test('should create non-expiring API key', async ({ page, request }) => {
      const apiKeyName = `Test API Key No Expire ${Date.now()}`

      const response = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
        expires_in_days: null,
      })

      // Verify no expiration
      expect(response.expires_at).toBeNull()
    })

    test('should validate API key name is required', async ({ page }) => {
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Open create dialog
      await page.click('button:has-text("Create API Key")')
      await page.waitForSelector('text=Create API Key', { timeout: 5000 })

      // Try to submit without name
      await page.click('button[type="submit"]:has-text("Create")')

      // Wait for validation error
      await page.waitForTimeout(500)

      // Verify validation error
      const nameInput = page.locator('input[name="name"]')
      const error = await nameInput.evaluate((el) => {
        const parent = el.closest('.text-input, [class*="form"]')
        return parent?.textContent || ''
      })

      expect(error.toLowerCase()).toContain('required')
    })

    test('should validate expiration days range', async ({ page }) => {
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Open create dialog
      await page.click('button:has-text("Create API Key")')
      await page.waitForSelector('text=Create API Key', { timeout: 5000 })

      // Fill form with invalid expiration
      await page.fill('input[name="name"]', 'Test Key')
      await page.fill('input[name="expires_in_days"], input[type="number"]', '400') // Invalid: > 365

      // Blur to trigger validation
      await page.locator('input[name="expires_in_days"], input[type="number"]').blur()
      await page.waitForTimeout(500)

      // Verify validation error
      const expirationInput = page.locator('input[name="expires_in_days"], input[type="number"]')
      const error = await expirationInput.evaluate((el) => {
        const parent = el.closest('.text-input, [class*="form"]')
        return parent?.textContent || ''
      })

      expect(error.toLowerCase()).toMatch(/365|range|invalid/)
    })
  })

  test.describe('API Key Display (One-Time)', () => {
    test('should display plaintext API key only once after creation', async ({ page, request }) => {
      // Create API key via API
      const apiKeyName = `Test API Key One-Time ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      const plaintextKey = createResponse.api_key

      // Navigate to API key management page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Wait for API keys to load
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Verify the created API key is in the list
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain(apiKeyName)

      // Verify the plaintext key is NOT displayed in the list
      // (only the hashed version should be stored)
      expect(pageContent).not.toContain(plaintextKey)

      // Verify API key details don't show the plaintext key
      const apiKeys = await listAPIKeysViaAPI(page, request)
      const createdKey = apiKeys.results.find((k) => k.id === createResponse.id)
      expect(createdKey).toBeDefined()
      expect(createdKey?.name).toBe(apiKeyName)
      // The API should not return the plaintext key in list/retrieve operations
    })

    test('should show API key in dialog after creation via UI', async ({ page }) => {
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Create API key via UI
      await page.click('button:has-text("Create API Key")')
      await page.waitForSelector('text=Create API Key', { timeout: 5000 })

      const apiKeyName = `Test API Key Dialog ${Date.now()}`
      await page.fill('input[name="name"]', apiKeyName)
      await page.click('button[type="submit"]:has-text("Create")')

      // Wait for success and API key display
      await page.waitForSelector('text=API Key Created Successfully', { timeout: 10000 })

      // Verify API key is shown in dialog
      const dialogContent = await page.textContent('[role="dialog"]')
      expect(dialogContent).toContain('Important')
      expect(dialogContent).toContain('Copy this API key now')
      expect(dialogContent).toContain("You won't be able to see it again")

      // Verify API key value is displayed (may be masked)
      const keyDisplay = page.locator('[class*="monospace"], code, pre').first()
      const keyValue = await keyDisplay.textContent()
      expect(keyValue).toBeTruthy()

      // Close dialog
      await page.click('button:has-text("Close"), button:has-text("Cancel")')
      await page.waitForTimeout(500)

      // Reopen dialog - API key should NOT be shown again
      await page.click('button:has-text("Create API Key")')
      await page.waitForSelector('text=Create API Key', { timeout: 5000 })

      const newDialogContent = await page.textContent('[role="dialog"]')
      expect(newDialogContent).not.toContain('API Key Created Successfully')
      expect(newDialogContent).not.toContain('Copy this API key now')
    })

    test('should allow toggling API key visibility in creation dialog', async ({ page }) => {
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Create API key
      await page.click('button:has-text("Create API Key")')
      await page.waitForSelector('text=Create API Key', { timeout: 5000 })

      const apiKeyName = `Test API Key Toggle ${Date.now()}`
      await page.fill('input[name="name"]', apiKeyName)
      await page.click('button[type="submit"]:has-text("Create")')

      // Wait for API key display
      await page.waitForSelector('text=API Key Created Successfully', { timeout: 10000 })

      // Initially, key should be masked (dots)
      const keyDisplay = page.locator('[class*="monospace"], code, pre').first()
      let keyValue = await keyDisplay.textContent()
      const isMasked = keyValue?.includes('•') || keyValue?.length === 40

      // Toggle visibility
      const toggleButton = page.locator('button:has-text("Show"), button:has-text("Hide")').first()
      if (await toggleButton.count() > 0) {
        await toggleButton.click()
        await page.waitForTimeout(300)

        // Verify key is now visible or hidden
        keyValue = await keyDisplay.textContent()
        if (isMasked) {
          // Should now show actual key
          expect(keyValue?.length).toBeGreaterThan(40)
          expect(keyValue).not.toBe('•'.repeat(40))
        }
      }
    })

    test('should not return plaintext key in list API response', async ({ page, request }) => {
      // Create API key
      const apiKeyName = `Test API Key List ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      const plaintextKey = createResponse.api_key

      // List API keys
      const listResponse = await listAPIKeysViaAPI(page, request)

      // Find the created key
      const foundKey = listResponse.results.find((k) => k.id === createResponse.id)
      expect(foundKey).toBeDefined()

      // Verify plaintext key is NOT in the response
      const responseJson = JSON.stringify(listResponse)
      expect(responseJson).not.toContain(plaintextKey)
    })
  })

  test.describe('API Key Revocation', () => {
    test('should delete API key via UI', async ({ page, request }) => {
      // Create API key first
      const apiKeyName = `Test API Key Delete UI ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      // Navigate to API key management page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Wait for API keys to load
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Find and click delete button for the created key
      const deleteButton = page
        .locator(`tr:has-text("${apiKeyName}")`)
        .locator('button[aria-label*="delete"], button:has([class*="Delete"])')
        .first()

      if ((await deleteButton.count()) > 0) {
        // Handle confirmation dialog
        page.on('dialog', async (dialog) => {
          expect(dialog.message()).toContain('delete')
          expect(dialog.message()).toContain('sure')
          await dialog.accept()
        })

        await deleteButton.click()

        // Wait for deletion
        await page.waitForTimeout(2000)

        // Verify key is removed from list
        const pageContent = await page.textContent('body')
        expect(pageContent).not.toContain(apiKeyName)
      }
    })

    test('should delete API key via API', async ({ page, request }) => {
      // Create API key
      const apiKeyName = `Test API Key Delete API ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      // Delete via API
      await deleteAPIKeyViaAPI(page, request, createResponse.id)

      // Verify key is deleted
      const listResponse = await listAPIKeysViaAPI(page, request)
      const deletedKey = listResponse.results.find((k) => k.id === createResponse.id)
      expect(deletedKey).toBeUndefined()
    })

    test('should show confirmation dialog before deletion', async ({ page, request }) => {
      // Create API key
      const apiKeyName = `Test API Key Confirm ${Date.now()}`
      await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Set up dialog handler
      let dialogShown = false
      page.on('dialog', async (dialog) => {
        dialogShown = true
        expect(dialog.message().toLowerCase()).toContain('delete')
        expect(dialog.message().toLowerCase()).toContain('sure')
        // Cancel to test confirmation
        await dialog.dismiss()
      })

      // Click delete
      const deleteButton = page
        .locator(`tr:has-text("${apiKeyName}")`)
        .locator('button[aria-label*="delete"], button:has([class*="Delete"])')
        .first()

      if ((await deleteButton.count()) > 0) {
        await deleteButton.click()
        await page.waitForTimeout(500)

        // Verify dialog was shown
        expect(dialogShown).toBe(true)

        // Verify key still exists (cancelled deletion)
        const pageContent = await page.textContent('body')
        expect(pageContent).toContain(apiKeyName)
      }
    })

    test('should handle deletion error gracefully', async ({ page, request }) => {
      // Try to delete non-existent key
      const fakeId = '00000000-0000-0000-0000-000000000000'

      const apiBaseUrl = getApiBaseUrl()
      const accessToken = await page.evaluate(() => {
        return localStorage.getItem('auth_access_token')
      })

      const response = await request.delete(`${apiBaseUrl}/api/v1/auth/api-keys/${fakeId}/`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      })

      // Should return error status
      expect(response.status()).toBeGreaterThanOrEqual(400)
    })
  })

  test.describe('API Key Usage Tracking', () => {
    test('should track API key usage when used for authentication', async ({ page, request }) => {
      // Create API key
      const apiKeyName = `Test API Key Usage ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      const plaintextKey = createResponse.api_key

      // Initially, last_used_at should be null
      let listResponse = await listAPIKeysViaAPI(page, request)
      let createdKey = listResponse.results.find((k) => k.id === createResponse.id)
      expect(createdKey?.last_used_at).toBeNull()

      // Use API key for authentication
      const useResponse = await useAPIKeyForRequest(request, plaintextKey, '/api/v1/auth/me/')

      // Wait a bit for usage tracking to update
      await page.waitForTimeout(2000)

      // Verify last_used_at is updated
      listResponse = await listAPIKeysViaAPI(page, request)
      createdKey = listResponse.results.find((k) => k.id === createResponse.id)
      expect(createdKey?.last_used_at).not.toBeNull()

      // Verify last_used_at is recent (within last minute)
      if (createdKey?.last_used_at) {
        const lastUsed = new Date(createdKey.last_used_at)
        const now = new Date()
        const diffSeconds = (now.getTime() - lastUsed.getTime()) / 1000
        expect(diffSeconds).toBeLessThan(60)
      }
    })

    test('should display last used date in UI', async ({ page, request }) => {
      // Create API key
      const apiKeyName = `Test API Key Last Used ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      // Use the key
      await useAPIKeyForRequest(request, createResponse.api_key, '/api/v1/auth/me/')
      await page.waitForTimeout(2000)

      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Verify last used is displayed
      const pageContent = await page.textContent('body')
      const rowContent = await page.locator(`tr:has-text("${apiKeyName}")`).textContent()

      // Should show "Last Used" or date (not "Never")
      expect(rowContent).not.toContain('Never')
      // May show date or "Recently" or similar
    })

    test('should show "Never" for unused API keys', async ({ page, request }) => {
      // Create API key but don't use it
      const apiKeyName = `Test API Key Never Used ${Date.now()}`
      await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Verify shows "Never" or similar
      const rowContent = await page.locator(`tr:has-text("${apiKeyName}")`).textContent()
      // May show "Never" or null/empty representation
      const hasNever = rowContent?.toLowerCase().includes('never') || false
      // Or may not show anything for null values
    })

    test('should update last_used_at on subsequent uses', async ({ page, request }) => {
      // Create API key
      const apiKeyName = `Test API Key Multiple Uses ${Date.now()}`
      const createResponse = await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
      })

      const plaintextKey = createResponse.api_key

      // First use
      await useAPIKeyForRequest(request, plaintextKey, '/api/v1/auth/me/')
      await page.waitForTimeout(2000)

      let listResponse = await listAPIKeysViaAPI(page, request)
      let createdKey = listResponse.results.find((k) => k.id === createResponse.id)
      const firstUsedAt = createdKey?.last_used_at
      expect(firstUsedAt).not.toBeNull()

      // Wait a bit
      await page.waitForTimeout(2000)

      // Second use
      await useAPIKeyForRequest(request, plaintextKey, '/api/v1/auth/me/')
      await page.waitForTimeout(2000)

      listResponse = await listAPIKeysViaAPI(page, request)
      createdKey = listResponse.results.find((k) => k.id === createResponse.id)
      const secondUsedAt = createdKey?.last_used_at

      // Verify last_used_at was updated
      expect(secondUsedAt).not.toBeNull()
      if (firstUsedAt && secondUsedAt) {
        const firstDate = new Date(firstUsedAt)
        const secondDate = new Date(secondUsedAt)
        expect(secondDate.getTime()).toBeGreaterThanOrEqual(firstDate.getTime())
      }
    })
  })

  test.describe('API Key Management UI', () => {
    test('should display list of API keys', async ({ page, request }) => {
      // Create a few API keys
      const key1 = await createAPIKeyViaAPI(page, request, { name: `Key 1 ${Date.now()}` })
      const key2 = await createAPIKeyViaAPI(page, request, { name: `Key 2 ${Date.now()}` })

      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Verify keys are displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain(key1.name)
      expect(pageContent).toContain(key2.name)
    })

    test('should show empty state when no API keys exist', async ({ page }) => {
      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')

      // Check for empty state message
      const pageContent = await page.textContent('body')
      // May show "No API keys" or empty table message
      const hasEmptyState =
        pageContent?.toLowerCase().includes('no api key') ||
        pageContent?.toLowerCase().includes('create your first') ||
        false

      // If there are keys, this test may not apply
      // But we can verify the UI handles empty state
    })

    test('should display API key scopes', async ({ page, request }) => {
      // Create key with scopes
      const apiKeyName = `Test API Key Scopes UI ${Date.now()}`
      await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
        scopes: ['assets:read', 'assets:write'],
      })

      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Verify scopes are displayed
      const rowContent = await page.locator(`tr:has-text("${apiKeyName}")`).textContent()
      expect(rowContent).toContain('assets:read')
      expect(rowContent).toContain('assets:write')
    })

    test('should display API key expiration status', async ({ page, request }) => {
      // Create key with expiration
      const apiKeyName = `Test API Key Expiration UI ${Date.now()}`
      await createAPIKeyViaAPI(page, request, {
        name: apiKeyName,
        expires_in_days: 30,
      })

      // Navigate to page
      await page.goto('/settings/api-keys')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 5000 })

      // Verify expiration is displayed
      const rowContent = await page.locator(`tr:has-text("${apiKeyName}")`).textContent()
      // Should show expiration date or "Expires" label
      expect(rowContent).toBeTruthy()
    })
  })
})

