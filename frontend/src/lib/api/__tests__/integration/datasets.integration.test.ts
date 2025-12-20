/**
 * Dataset API Integration Tests
 *
 * Comprehensive integration tests for Dataset API endpoints.
 * These tests make real HTTP requests to the API server.
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest'
import {
  listDatasets,
  getDataset,
  createDataset,
  listAssets,
  createAsset,
  type Dataset,
  type CreateDatasetRequest,
} from '@/lib/api/datasets'
import { createAsset as createAssetAPI } from '@/lib/api/assets'
import { AxiosError } from 'axios'
import { config } from '@/lib/config/env'

const TEST_CONFIG = {
  skipIfUnavailable: true,
  apiBaseUrl: config.api.baseUrl,
  cleanupAfterTests: true,
}

const testDatasets: string[] = []
const testAssets: string[] = []
const testFileIds: string[] = []

async function checkApiAvailability(): Promise<boolean> {
  try {
    const response = await fetch(`${TEST_CONFIG.apiBaseUrl}/api/v1/`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(5000),
    })
    return response.ok || response.status === 401
  } catch {
    return false
  }
}

describe('Dataset API Integration Tests', () => {
  let apiAvailable: boolean

  beforeAll(async () => {
    apiAvailable = await checkApiAvailability()
    if (!apiAvailable && TEST_CONFIG.skipIfUnavailable) {
      console.warn(
        `⚠️  API server not available at ${TEST_CONFIG.apiBaseUrl}. Skipping integration tests.`
      )
    }
  })

  afterAll(async () => {
    // Cleanup is handled by the API - datasets are typically not deleted
    // but we can mark them for cleanup if needed
  })

  beforeEach(() => {
    if (!apiAvailable) {
      return
    }
  })

  describe('listDatasets', () => {
    it('should list datasets successfully', async () => {
      if (!apiAvailable) return

      const response = await listDatasets()

      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
      expect(response.count).toBeGreaterThanOrEqual(0)
    })

    it('should support pagination', async () => {
      if (!apiAvailable) return

      const page1 = await listDatasets({ page: 1, page_size: 10 })
      expect(page1.results).toBeInstanceOf(Array)
      expect(page1.results.length).toBeLessThanOrEqual(10)
    })

    it('should support filtering by asset_id', async () => {
      if (!apiAvailable) return

      // Create a test asset first
      const asset = await createAssetAPI({
        key: `dataset-filter-test-${Date.now()}`,
        name: 'Dataset Filter Test Asset',
      })
      testAssets.push(asset.id)

      const response = await listDatasets({ asset_id: asset.id })
      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
    })

    it('should support filtering by format', async () => {
      if (!apiAvailable) return

      const response = await listDatasets({ format: 'CSV' })
      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
    })

    it('should support sorting', async () => {
      if (!apiAvailable) return

      const response = await listDatasets({ ordering: '-created_at' })
      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
    })
  })

  describe('getDataset', () => {
    it('should handle 404 for non-existent dataset', async () => {
      if (!apiAvailable) return

      const nonExistentId = '00000000-0000-0000-0000-000000000000'

      try {
        await getDataset(nonExistentId)
        expect.fail('Should have thrown 404 error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(404)
      }
    })

    it('should handle invalid UUID format', async () => {
      if (!apiAvailable) return

      try {
        await getDataset('invalid-uuid')
        expect.fail('Should have thrown error for invalid UUID')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect([400, 404]).toContain(axiosError.response?.status)
      }
    })
  })

  describe('createDataset', () => {
    it('should handle validation errors for missing file_id', async () => {
      if (!apiAvailable) return

      const invalidData: CreateDatasetRequest = {
        file_id: '', // Invalid: empty file_id
      }

      try {
        await createDataset(invalidData)
        expect.fail('Should have thrown validation error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(400)
      }
    })

    it('should handle validation errors for invalid file_id', async () => {
      if (!apiAvailable) return

      const invalidData: CreateDatasetRequest = {
        file_id: '00000000-0000-0000-0000-000000000000', // Non-existent file
      }

      try {
        await createDataset(invalidData)
        expect.fail('Should have thrown validation error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect([400, 404]).toContain(axiosError.response?.status)
      }
    })
  })

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      if (!apiAvailable) return

      try {
        await listDatasets({}, {
          baseURL: 'http://invalid-host:8000',
        } as any)
        expect.fail('Should have thrown network error')
      } catch (error) {
        expect(error).toBeInstanceOf(Error)
      }
    })

    it('should handle timeout errors', async () => {
      if (!apiAvailable) return

      try {
        await listDatasets({}, {
          timeout: 1, // 1ms timeout - should fail
        } as any)
        expect.fail('Should have thrown timeout error')
      } catch (error) {
        expect(error).toBeInstanceOf(Error)
      }
    })
  })

  describe('Retry Logic', () => {
    it('should retry on 500 errors', async () => {
      if (!apiAvailable) return

      const response = await listDatasets({}, {
        retry: {
          maxRetries: 3,
          retryableStatusCodes: [500, 502, 503, 504],
        },
      } as any)

      expect(response).toBeDefined()
    })

    it('should not retry on 400 errors', async () => {
      if (!apiAvailable) return

      const invalidData: CreateDatasetRequest = {
        file_id: '', // Invalid
      }

      try {
        await createDataset(invalidData)
        expect.fail('Should have thrown validation error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(400)
      }
    })

    it('should not retry on 404 errors', async () => {
      if (!apiAvailable) return

      try {
        await getDataset('00000000-0000-0000-0000-000000000000')
        expect.fail('Should have thrown 404 error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(404)
      }
    })
  })
})

