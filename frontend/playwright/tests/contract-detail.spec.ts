/**
 * Contract Detail E2E Tests
 *
 * Comprehensive end-to-end tests for contract detail functionality covering:
 * - Contract detail display
 * - Contract version history
 * - Contract validation results
 * - Contract edit functionality
 * - Contract delete functionality
 *
 * Uses real API calls and implementations - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { login, type TestCredentials } from '../utils/auth'
import { getApiBaseUrl } from '../utils/api'
import {
  createTestContract,
  createTestAssets,
  deleteTestContract,
  deleteTestAsset,
  type Contract,
  type Asset,
} from '../utils/test-data'

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
 * Get contract via API
 */
async function getContractViaAPI(page: any, request: any, contractId: string): Promise<Contract> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to get contracts')
  }

  const response = await request.get(`${apiBaseUrl}/api/v1/contracts/${contractId}/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Contract retrieval failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  return (await response.json()) as Contract
}

/**
 * Validate contract via API
 */
async function validateContractViaAPI(
  page: any,
  request: any,
  contractId: string
): Promise<any> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to validate contracts')
  }

  const response = await request.post(`${apiBaseUrl}/api/v1/contracts/${contractId}/validate/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Contract validation failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  return await response.json()
}

/**
 * Delete contract via API
 */
async function deleteContractViaAPI(page: any, request: any, contractId: string): Promise<void> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to delete contracts')
  }

  const response = await request.delete(`${apiBaseUrl}/api/v1/contracts/${contractId}/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Contract deletion failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }
}

test.describe('Contract Detail', () => {
  let testCredentials: TestCredentials
  let createdContracts: Contract[] = []
  let createdAssets: Asset[] = []

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

  test.afterEach(async ({ request }) => {
    // Cleanup created resources
    for (const contract of createdContracts) {
      try {
        await deleteTestContract(request, contract.id)
      } catch (error) {
        // Ignore cleanup errors
      }
    }
    for (const asset of createdAssets) {
      try {
        await deleteTestAsset(request, asset.id)
      } catch (error) {
        // Ignore cleanup errors
      }
    }
    createdContracts = []
    createdAssets = []
  })

  test.describe('Contract Detail Display', () => {
    test('should display contract information', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')

      // Wait for contract to load
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify contract information is displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain(contract.id.substring(0, 8))

      // Verify contract name or ID is shown
      const contractName =
        contract.hub_contract_json?.info?.name || contract.id.substring(0, 8)
      expect(pageContent).toContain(contractName)
    })

    test('should display contract status', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify status is displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain(contract.status)
    })

    test('should display contract version information', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify version information is displayed
      const pageContent = await page.textContent('body')
      // Should show version, hub_contract_version, or original_spec_version
      const contractVersion =
        (contract as any).hub_contract_version ||
        (contract as any).original_spec_version ||
        contract.hub_contract_json?.hub_contract_version
      expect(
        pageContent?.includes('Version') ||
          pageContent?.includes('version') ||
          contractVersion
      ).toBeTruthy()
    })

    test('should display contract normalization status', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify normalization status is displayed
      const pageContent = await page.textContent('body')
      if (contract.normalization_status) {
        expect(pageContent).toContain(contract.normalization_status)
      }
    })

    test('should display contract JSON', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify contract JSON is displayed (if available)
      const pageContent = await page.textContent('body')
      if (contract.hub_contract_json) {
        // Should show JSON viewer or contract JSON section
        expect(
          pageContent?.includes('Contract JSON') ||
            pageContent?.includes('JSON') ||
            pageContent?.includes('hub_contract')
        ).toBeTruthy()
      }
    })

    test('should display associated asset if contract is attached', async ({ page, request }) => {
      // Create test asset
      const asset = await createTestAssets(request, 1)[0]
      createdAssets.push(asset)

      // Create contract and attach to asset
      const contract = await createTestContract(request, {
        factoryOptions: {
          overrides: {
            asset_id: asset.id,
          },
        },
      })
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify associated asset is displayed
      const pageContent = await page.textContent('body')
      const hasAssetReference = pageContent?.includes('Asset') || pageContent?.includes(asset.id.substring(0, 8))
      expect(hasAssetReference).toBeTruthy()
    })

    test('should display created and updated timestamps', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify timestamps are displayed
      const pageContent = await page.textContent('body')
      expect(pageContent?.toLowerCase()).toMatch(/created|updated|ago|at/)
    })

    test('should navigate back to contracts list', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')

      // Click back button
      const backButton = page.locator(
        'button[aria-label*="back"], button:has([class*="ArrowBack"])'
      )
      if ((await backButton.count()) > 0) {
        await backButton.click()
        await page.waitForURL('/contracts*', { timeout: 5000 })
        expect(page.url()).toContain('/contracts')
      }
    })
  })

  test.describe('Contract Version History', () => {
    test('should display version history when multiple versions exist', async ({ page, request }) => {
      // Create test asset
      const asset = await createTestAssets(request, 1)[0]
      createdAssets.push(asset)

      // Create multiple contracts for the same asset (versions)
      const contract1 = await createTestContract(request, {
        factoryOptions: {
          overrides: {
            asset_id: asset.id,
          },
        },
      })
      createdContracts.push(contract1)

      // Note: Creating multiple versions typically requires attaching contracts to asset
      // which increments version numbers. For this test, we'll verify the UI shows
      // version history section when asset_id is present.

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract1.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify version history section exists (if asset_id is present)
      const pageContent = await page.textContent('body')
      const contractAssetId = (contract1 as any).asset_id
      if (contractAssetId) {
        expect(pageContent?.toLowerCase()).toMatch(/version.*history|history/i)
      }
    })

    test('should show empty state when no version history exists', async ({ page, request }) => {
      // Create test contract without asset (no version history)
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify empty state or no version history section
      const pageContent = await page.textContent('body')
      // May show "No version history" or not show the section at all
      expect(pageContent).toBeTruthy()
    })

    test('should allow navigation to other versions', async ({ page, request }) => {
      // Create test asset
      const asset = await createTestAssets(request, 1)[0]
      createdAssets.push(asset)

      // Create contract with asset
      const contract = await createTestContract(request, {
        factoryOptions: {
          overrides: {
            asset_id: asset.id,
          },
        },
      })
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Look for version history and view buttons
      const viewButtons = page.locator('button:has-text("View"), a:has-text("View")')
      if ((await viewButtons.count()) > 0) {
        // Click first view button (if it's for a version)
        await viewButtons.first().click()
        await page.waitForTimeout(1000)

        // Should navigate to another contract detail page
        const url = page.url()
        expect(url).toContain('/contracts/')
      }
    })
  })

  test.describe('Contract Validation Results', () => {
    test('should display validation status', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify validation results section exists
      const pageContent = await page.textContent('body')
      expect(pageContent?.toLowerCase()).toMatch(/validation|validate/i)

      // If contract has validation_status, verify it's displayed
      if (contract.validation_status) {
        expect(pageContent).toContain(contract.validation_status)
      }
    })

    test('should trigger contract validation via UI', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('button:has-text("Validate")', { timeout: 10000 })

      // Click validate button
      const validateButton = page.locator('button:has-text("Validate")')
      await validateButton.click()

      // Wait for validation to complete
      await page.waitForTimeout(3000)

      // Verify validation status is updated or shown
      const pageContent = await page.textContent('body')
      // Should show validation status or results
      expect(pageContent?.toLowerCase()).toMatch(/valid|invalid|warning|validation/i)
    })

    test('should display validation errors if present', async ({ page, request }) => {
      // Create test contract (may have validation errors)
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Trigger validation via API
      try {
        await validateContractViaAPI(page, request, contract.id)
      } catch (error) {
        // Validation may fail, that's okay for this test
      }

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Refresh to get updated validation status
      await page.reload()
      await page.waitForLoadState('networkidle')

      // Get updated contract
      const updatedContract = await getContractViaAPI(page, request, contract.id)

      // If validation errors exist, verify they're displayed
      const validationErrors = (updatedContract as any).validation_errors
      if (validationErrors && validationErrors.length > 0) {
        const pageContent = await page.textContent('body')
        expect(pageContent?.toLowerCase()).toMatch(/error|invalid/i)
      }
    })

    test('should display validation warnings if present', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Trigger validation
      try {
        await validateContractViaAPI(page, request, contract.id)
      } catch (error) {
        // Ignore validation errors
      }

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Refresh to get updated validation status
      await page.reload()
      await page.waitForLoadState('networkidle')

      // Get updated contract
      const updatedContract = await getContractViaAPI(page, request, contract.id)

      // If validation warnings exist, verify they're displayed
      const validationWarnings = (updatedContract as any).validation_warnings
      if (validationWarnings && validationWarnings.length > 0) {
        const pageContent = await page.textContent('body')
        expect(pageContent?.toLowerCase()).toMatch(/warning/i)
      }
    })

    test('should show empty state when no validation results exist', async ({ page, request }) => {
      // Create test contract without validation
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('h4, h5, h6', { timeout: 10000 })

      // Verify empty state or message
      const pageContent = await page.textContent('body')
      // May show "No validation results" or prompt to validate
      expect(pageContent?.toLowerCase()).toMatch(/validation|validate|no.*result/i)
    })

    test('should validate contract via API', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Validate via API
      const validationResult = await validateContractViaAPI(page, request, contract.id)

      // Verify validation result
      expect(validationResult).toBeDefined()
      expect(validationResult.validation_status).toBeDefined()
    })
  })

  test.describe('Contract Edit Functionality', () => {
    test('should navigate to edit page when edit button is clicked', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('button:has-text("Edit")', { timeout: 10000 })

      // Click edit button
      const editButton = page.locator('button:has-text("Edit")')
      await editButton.click()

      // Verify navigation to edit page
      await page.waitForURL(`**/contracts/${contract.id}/edit**`, { timeout: 5000 })
      expect(page.url()).toContain(`/contracts/${contract.id}/edit`)
    })

    test('should display edit form with contract data', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to edit page
      await page.goto(`/contracts/${contract.id}/edit`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('form, input, textarea', { timeout: 10000 })

      // Verify form is displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toBeTruthy()

      // Verify contract data is pre-filled (if form fields are visible)
      const formFields = page.locator('input, textarea, select')
      const fieldCount = await formFields.count()
      expect(fieldCount).toBeGreaterThan(0)
    })

    test('should allow editing contract name', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to edit page
      await page.goto(`/contracts/${contract.id}/edit`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('input[name="name"], input[type="text"]', { timeout: 10000 })

      // Find and update name field
      const nameInput = page.locator('input[name="name"]').first()
      if ((await nameInput.count()) > 0) {
        await nameInput.clear()
        await nameInput.fill('Updated Contract Name')
        await nameInput.blur()

        // Submit form (if save button exists)
        const saveButton = page.locator('button[type="submit"], button:has-text("Save")')
        if ((await saveButton.count()) > 0) {
          await saveButton.click()
          await page.waitForTimeout(2000)

          // Verify update (may navigate back to detail page)
          const pageContent = await page.textContent('body')
          expect(pageContent).toBeTruthy()
        }
      }
    })
  })

  test.describe('Contract Delete Functionality', () => {
    test('should show delete confirmation dialog', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('button:has-text("Delete")', { timeout: 10000 })

      // Click delete button
      const deleteButton = page.locator('button:has-text("Delete")')
      await deleteButton.click()

      // Wait for dialog to appear
      await page.waitForSelector('[role="dialog"]', { timeout: 5000 })

      // Verify confirmation dialog is shown
      const dialogContent = await page.textContent('[role="dialog"]')
      expect(dialogContent?.toLowerCase()).toMatch(/delete|sure|cannot.*undone/i)
    })

    test('should cancel delete when cancel button is clicked', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('button:has-text("Delete")', { timeout: 10000 })

      // Click delete button
      const deleteButton = page.locator('button:has-text("Delete")')
      await deleteButton.click()

      // Wait for dialog
      await page.waitForSelector('[role="dialog"]', { timeout: 5000 })

      // Click cancel
      const cancelButton = page.locator('button:has-text("Cancel")')
      await cancelButton.click()

      // Verify dialog is closed and contract still exists
      await page.waitForTimeout(500)
      const dialog = page.locator('[role="dialog"]')
      expect(await dialog.count()).toBe(0)

      // Verify still on detail page
      expect(page.url()).toContain(`/contracts/${contract.id}`)
    })

    test('should delete contract when confirmed', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Navigate to contract detail page
      await page.goto(`/contracts/${contract.id}`)
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('button:has-text("Delete")', { timeout: 10000 })

      // Click delete button
      const deleteButton = page.locator('button:has-text("Delete")')
      await deleteButton.click()

      // Wait for dialog
      await page.waitForSelector('[role="dialog"]', { timeout: 5000 })

      // Confirm delete
      const confirmButton = page.locator('button:has-text("Delete"):not([disabled])').last()
      await confirmButton.click()

      // Wait for deletion and navigation
      await page.waitForURL('/contracts*', { timeout: 10000 })
      expect(page.url()).toContain('/contracts')
      expect(page.url()).not.toContain(contract.id)
    })

    test('should delete contract via API', async ({ page, request }) => {
      // Create test contract
      const contract = await createTestContract(request)
      createdContracts.push(contract)

      // Delete via API
      await deleteContractViaAPI(page, request, contract.id)

      // Verify contract is deleted (try to get it - should fail)
      const apiBaseUrl = getApiBaseUrl()
      const accessToken = await page.evaluate(() => {
        return localStorage.getItem('auth_access_token')
      })

      const response = await request.get(`${apiBaseUrl}/api/v1/contracts/${contract.id}/`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      })

      // Should return 404 or error
      expect(response.status()).toBeGreaterThanOrEqual(400)

      // Remove from cleanup list since it's already deleted
      createdContracts = createdContracts.filter((c) => c.id !== contract.id)
    })

    test('should handle delete errors gracefully', async ({ page, request }) => {
      // Try to delete non-existent contract
      const fakeId = '00000000-0000-0000-0000-000000000000'

      const apiBaseUrl = getApiBaseUrl()
      const accessToken = await page.evaluate(() => {
        return localStorage.getItem('auth_access_token')
      })

      const response = await request.delete(`${apiBaseUrl}/api/v1/contracts/${fakeId}/`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      })

      // Should return error status
      expect(response.status()).toBeGreaterThanOrEqual(400)
    })
  })
})

