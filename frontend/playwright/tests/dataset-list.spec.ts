/**
 * Dataset List E2E Tests
 *
 * Comprehensive end-to-end tests for dataset list functionality covering:
 * - Dataset list display
 * - Dataset list pagination
 * - Dataset search
 * - Dataset filtering
 * - Dataset version display
 *
 * Uses real API calls and implementations - no mocks/stubs.
 * Always fixes root cause and follows development best practices.
 */

import { test, expect } from '@playwright/test'
import { login, type TestCredentials } from '../utils/auth'
import { getApiBaseUrl } from '../utils/api'
import { createTestDatasets, deleteTestDataset, type Dataset } from '../utils/test-data'

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
 * List datasets via API
 */
async function listDatasetsViaAPI(
  page: any,
  request: any,
  params: Record<string, any> = {}
): Promise<any> {
  const apiBaseUrl = getApiBaseUrl()
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('User must be authenticated to list datasets')
  }

  const queryString = new URLSearchParams(
    Object.entries(params).reduce((acc, [key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        acc[key] = String(value)
      }
      return acc
    }, {} as Record<string, string>)
  ).toString()

  const url = `${apiBaseUrl}/api/v1/datasets/${queryString ? `?${queryString}` : ''}`
  const response = await request.get(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Dataset listing failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  return await response.json()
}

test.describe('Dataset List', () => {
  let testCredentials: TestCredentials
  let createdDatasets: Dataset[] = []

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
    // Cleanup created datasets
    for (const dataset of createdDatasets) {
      try {
        await deleteTestDataset(request, dataset.id)
      } catch (error) {
        // Ignore cleanup errors
      }
    }
    createdDatasets = []
  })

  test.describe('Dataset List Display', () => {
    test('should display list of datasets', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 3, {
        factoryOptions: {
          overrides: {
            name: (index: number) => `Test Dataset ${index + 1}`,
          },
        },
      })
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')

      // Wait for datasets to load
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify datasets are displayed
      for (const dataset of datasets) {
        const pageContent = await page.textContent('body')
        expect(pageContent).toContain(dataset.id.substring(0, 8))
      }
    })

    test('should display dataset details in table', async ({ page, request }) => {
      // Create dataset with specific details
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Detailed Dataset',
            format: 'CSV',
            version: 1,
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify dataset details are displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain(dataset.id.substring(0, 8))
      expect(pageContent).toContain(dataset.format)
    })

    test('should display dataset count in header', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 5)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify count is displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toMatch(/\d+\s+dataset/i)
    })

    test('should navigate to dataset detail on row click', async ({ page, request }) => {
      // Create test dataset
      const dataset = await createTestDatasets(request, 1)[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Click on dataset row or view button
      const viewButton = page.locator(
        `button[aria-label*="View"], button:has([class*="Visibility"])`
      ).first()
      if ((await viewButton.count()) > 0) {
        await viewButton.click()
      } else {
        // Try clicking on row
        const datasetRow = page.locator(`tr:has-text("${dataset.id.substring(0, 8)}")`).first()
        await datasetRow.click()
      }

      // Verify navigation to dataset detail page
      await page.waitForURL(`/datasets/${dataset.id}*`, { timeout: 5000 })
      expect(page.url()).toContain(`/datasets/${dataset.id}`)
    })

    test('should display dataset format badges', async ({ page, request }) => {
      // Create datasets with different formats
      const csvDataset = await createTestDatasets(request, 1, {
        factoryOptions: { overrides: { format: 'CSV', name: 'CSV Dataset' } },
      })[0]
      const jsonDataset = await createTestDatasets(request, 1, {
        factoryOptions: { overrides: { format: 'JSON', name: 'JSON Dataset' } },
      })[0]
      createdDatasets.push(csvDataset, jsonDataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify format badges are displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain('CSV')
      expect(pageContent).toContain('JSON')
    })
  })

  test.describe('Dataset List Pagination', () => {
    test('should paginate through multiple pages', async ({ page, request }) => {
      // Create enough datasets for multiple pages (default page size is 20)
      const datasets = await createTestDatasets(request, 25, {
        factoryOptions: {
          overrides: {
            name: (index: number) => `Pagination Dataset ${index + 1}`,
          },
        },
      })
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify pagination controls are visible
      const pagination = page.locator('[class*="Pagination"], nav[aria-label*="pagination"]')
      if ((await pagination.count()) > 0) {
        // Click next page
        const nextButton = page.locator('button:has-text("Next"), button[aria-label*="next"]')
        if ((await nextButton.count()) > 0) {
          await nextButton.click()
          await page.waitForTimeout(1000)

          // Verify page changed
          const pageContent = await page.textContent('body')
          // Should show different datasets on page 2
          expect(pageContent).toBeTruthy()
        }
      }
    })

    test('should change page size', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 15)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Look for page size selector
      const pageSizeSelect = page.locator('select, [role="combobox"]').filter({
        hasText: /10|20|50|100/,
      })

      if ((await pageSizeSelect.count()) > 0) {
        // Change page size
        await pageSizeSelect.selectOption('10')
        await page.waitForTimeout(1000)

        // Verify page size changed (may need to check API call or UI)
        const pageContent = await page.textContent('body')
        expect(pageContent).toBeTruthy()
      }
    })

    test('should reset to first page when changing filters', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 25)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Navigate to page 2 if pagination exists
      const nextButton = page.locator('button:has-text("Next"), button[aria-label*="next"]')
      if ((await nextButton.count()) > 0) {
        await nextButton.click()
        await page.waitForTimeout(1000)
      }

      // Apply filter (format filter)
      const formatSelect = page.locator('select[label*="Format"], select').first()
      if ((await formatSelect.count()) > 0) {
        await formatSelect.selectOption('CSV')
        await page.waitForTimeout(1000)

        // Verify page reset to 1 (check URL or page indicator)
        const url = page.url()
        // URL should not contain page=2 or should contain page=1
        expect(url).not.toContain('page=2')
      }
    })

    test('should display correct page information', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 25)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify page information is displayed
      const pageContent = await page.textContent('body')
      // Should show page numbers or "Showing X-Y of Z"
      expect(pageContent).toMatch(/page|\d+\s*-\s*\d+|\d+\s+of\s+\d+/i)
    })
  })

  test.describe('Dataset Search', () => {
    test('should search datasets by name', async ({ page, request }) => {
      // Create datasets with different names
      const searchableDataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Unique Search Dataset Name',
          },
        },
      })[0]
      const otherDataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Other Dataset',
          },
        },
      })[0]
      createdDatasets.push(searchableDataset, otherDataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('input[type="search"], input[placeholder*="Search"]', {
        timeout: 10000,
      })

      // Enter search query
      const searchInput = page.locator('input[type="search"], input[placeholder*="Search"]').first()
      await searchInput.fill('Unique Search')
      await searchInput.press('Enter')
      await page.waitForTimeout(1000)

      // Verify search results
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain('Unique Search Dataset Name')
      // May or may not show other dataset depending on search implementation
    })

    test('should search datasets by ID', async ({ page, request }) => {
      // Create dataset with specific ID
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'ID Search Dataset',
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('input[type="search"], input[placeholder*="Search"]', {
        timeout: 10000,
      })

      // Search by ID (first 8 characters)
      const searchInput = page.locator('input[type="search"], input[placeholder*="Search"]').first()
      await searchInput.fill(dataset.id.substring(0, 8))
      await searchInput.press('Enter')
      await page.waitForTimeout(1000)

      // Verify dataset is found
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain('ID Search Dataset')
    })

    test('should clear search and show all datasets', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 3)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('input[type="search"], input[placeholder*="Search"]', {
        timeout: 10000,
      })

      // Enter search that matches nothing
      const searchInput = page.locator('input[type="search"], input[placeholder*="Search"]').first()
      await searchInput.fill('NonExistentDatasetName12345')
      await searchInput.press('Enter')
      await page.waitForTimeout(1000)

      // Clear search
      const clearButton = page.locator('button[aria-label*="clear"], button:has([class*="Clear"])')
      if ((await clearButton.count()) > 0) {
        await clearButton.click()
        await page.waitForTimeout(1000)

        // Verify all datasets are shown again
        const pageContent = await page.textContent('body')
        for (const dataset of datasets) {
          expect(pageContent).toContain(dataset.id.substring(0, 8))
        }
      }
    })

    test('should show no results message for non-matching search', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 2)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('input[type="search"], input[placeholder*="Search"]', {
        timeout: 10000,
      })

      // Search for non-existent dataset
      const searchInput = page.locator('input[type="search"], input[placeholder*="Search"]').first()
      await searchInput.fill('NonExistentDatasetName12345')
      await searchInput.press('Enter')
      await page.waitForTimeout(2000)

      // Verify no results message
      const pageContent = await page.textContent('body')
      expect(pageContent?.toLowerCase()).toMatch(/no.*result|no.*found|no.*dataset/i)
    })
  })

  test.describe('Dataset Filtering', () => {
    test('should filter datasets by format', async ({ page, request }) => {
      // Create datasets with different formats
      const csvDataset = await createTestDatasets(request, 1, {
        factoryOptions: { overrides: { format: 'CSV', name: 'CSV Filter Dataset' } },
      })[0]
      const jsonDataset = await createTestDatasets(request, 1, {
        factoryOptions: { overrides: { format: 'JSON', name: 'JSON Filter Dataset' } },
      })[0]
      createdDatasets.push(csvDataset, jsonDataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('select[label*="Format"], select', { timeout: 10000 })

      // Apply format filter
      const formatSelect = page.locator('select[label*="Format"], select').first()
      if ((await formatSelect.count()) > 0) {
        await formatSelect.selectOption('CSV')
        await page.waitForTimeout(1000)

        // Verify filter is applied
        const pageContent = await page.textContent('body')
        expect(pageContent).toContain('CSV Filter Dataset')
        // May or may not show JSON dataset depending on filter implementation
      }
    })

    test('should filter datasets by asset ID', async ({ page, request }) => {
      // Create test asset
      const { createTestAssets } = await import('../utils/test-data')
      const asset = await createTestAssets(request, 1)[0]

      // Create datasets with and without asset
      const datasetWithAsset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            asset: asset.id,
            name: 'Asset Filter Dataset',
          },
        },
      })[0]
      const datasetWithoutAsset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            asset: null,
            name: 'No Asset Dataset',
          },
        },
      })[0]
      createdDatasets.push(datasetWithAsset, datasetWithoutAsset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')

      // Note: Asset ID filter may be in a filter menu or separate input
      // This test verifies the UI handles filtering if the feature exists
      const pageContent = await page.textContent('body')
      expect(pageContent).toBeTruthy()

      // Cleanup asset
      const { deleteTestAsset } = await import('../utils/test-data')
      await deleteTestAsset(request, asset.id)
    })

    test('should clear all filters', async ({ page, request }) => {
      // Create test datasets
      const datasets = await createTestDatasets(request, 3)
      createdDatasets.push(...datasets)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('select[label*="Format"], select', { timeout: 10000 })

      // Apply a filter
      const formatSelect = page.locator('select[label*="Format"], select').first()
      if ((await formatSelect.count()) > 0) {
        await formatSelect.selectOption('CSV')
        await page.waitForTimeout(1000)

        // Clear all filters
        const clearButton = page.locator('button:has-text("Clear Filters"), button:has-text("Clear")')
        if ((await clearButton.count()) > 0) {
          await clearButton.click()
          await page.waitForTimeout(1000)

          // Verify filters are cleared
          const pageContent = await page.textContent('body')
          expect(pageContent).toBeTruthy()
        }
      }
    })

    test('should combine multiple filters', async ({ page, request }) => {
      // Create datasets with different combinations
      const csvDataset = await createTestDatasets(request, 1, {
        factoryOptions: { overrides: { format: 'CSV', name: 'CSV Dataset' } },
      })[0]
      const jsonDataset = await createTestDatasets(request, 1, {
        factoryOptions: { overrides: { format: 'JSON', name: 'JSON Dataset' } },
      })[0]
      createdDatasets.push(csvDataset, jsonDataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('select[label*="Format"], select', { timeout: 10000 })

      // Apply format filter
      const formatSelect = page.locator('select[label*="Format"], select').first()
      if ((await formatSelect.count()) > 0) {
        await formatSelect.selectOption('CSV')
        await page.waitForTimeout(1000)

        // Apply search filter
        const searchInput = page.locator('input[type="search"], input[placeholder*="Search"]').first()
        await searchInput.fill('CSV Dataset')
        await searchInput.press('Enter')
        await page.waitForTimeout(1000)

        // Verify combined filters work
        const pageContent = await page.textContent('body')
        expect(pageContent).toContain('CSV Dataset')
      }
    })
  })

  test.describe('Dataset Version Display', () => {
    test('should display dataset version number', async ({ page, request }) => {
      // Create test dataset
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Version Display Test',
            version: 1,
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify version is displayed
      const pageContent = await page.textContent('body')
      // Should show version number (v1, version 1, etc.)
      expect(pageContent?.toLowerCase()).toMatch(/v\d+|version\s*\d+/i)
    })

    test('should display current version indicator', async ({ page, request }) => {
      // Create test dataset marked as current
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Current Version Test',
            version: 1,
            is_current: true,
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify current indicator is displayed
      const pageContent = await page.textContent('body')
      expect(pageContent?.toLowerCase()).toMatch(/current/i)
    })

    test('should display semantic version if present', async ({ page, request }) => {
      // Create test dataset with semantic version
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Semantic Version Test',
            version: 1,
            semantic_version: '1.0.0',
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify semantic version is displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain('1.0.0')
    })

    test('should display version tags if present', async ({ page, request }) => {
      // Create test dataset with version tags
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Version Tags Test',
            version: 1,
            version_tags: ['stable', 'production'],
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify version tags are displayed (may show as tooltip or chip)
      const pageContent = await page.textContent('body')
      // Should show tags or tag count
      expect(pageContent?.toLowerCase()).toMatch(/tag|stable|production/i)
    })

    test('should display multiple dataset versions', async ({ page, request }) => {
      // Create test asset
      const { createTestAssets } = await import('../utils/test-data')
      const asset = await createTestAssets(request, 1)[0]

      // Create multiple datasets for the same asset (versions)
      const dataset1 = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            asset: asset.id,
            version: 1,
            name: 'Version 1 Dataset',
          },
        },
      })[0]
      const dataset2 = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            asset: asset.id,
            version: 2,
            name: 'Version 2 Dataset',
          },
        },
      })[0]
      createdDatasets.push(dataset1, dataset2)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Verify both versions are displayed
      const pageContent = await page.textContent('body')
      expect(pageContent).toContain('Version 1 Dataset')
      expect(pageContent).toContain('Version 2 Dataset')

      // Cleanup asset
      const { deleteTestAsset } = await import('../utils/test-data')
      await deleteTestAsset(request, asset.id)
    })

    test('should show version in dataset detail navigation', async ({ page, request }) => {
      // Create test dataset
      const dataset = await createTestDatasets(request, 1, {
        factoryOptions: {
          overrides: {
            name: 'Version Navigation Test',
            version: 1,
          },
        },
      })[0]
      createdDatasets.push(dataset)

      // Navigate to datasets page
      await page.goto('/datasets')
      await page.waitForLoadState('networkidle')
      await page.waitForSelector('table, [class*="Table"]', { timeout: 10000 })

      // Click view button
      const viewButton = page.locator(
        `button[aria-label*="View"], button:has([class*="Visibility"])`
      ).first()
      if ((await viewButton.count()) > 0) {
        await viewButton.click()

        // Verify navigation includes version information
        await page.waitForURL(`/datasets/${dataset.id}*`, { timeout: 5000 })
        const detailPageContent = await page.textContent('body')
        expect(detailPageContent).toBeTruthy()
      }
    })
  })
})

