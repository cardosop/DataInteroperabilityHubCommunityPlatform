/**
 * Mock Utilities Tests
 *
 * Tests for mock API utilities and test data factories.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  createMockResponse,
  createMockPaginatedResponse,
  createMockError,
  createMockNetworkError,
  createMockApiErrorResponse,
} from '../mocks/api'
import {
  createTestAsset,
  createTestAssets,
  createTestContract,
  createTestContracts,
  createTestJob,
  createTestJobs,
  createTestDataset,
  createTestDatasets,
  createTestUser,
  createTestTenant,
  resetIdCounter,
} from '../mocks/data'

describe('mock API utilities', () => {
  describe('createMockResponse', () => {
    it('should create a mock response with data', () => {
      const response = createMockResponse({ id: '1', name: 'Test' })
      expect(response.data).toEqual({ id: '1', name: 'Test' })
      expect(response.status).toBe(200)
    })

    it('should create a mock response with custom status', () => {
      const response = createMockResponse({ error: 'Not found' }, 404)
      expect(response.status).toBe(404)
    })

    it('should create a mock response with custom headers', () => {
      const response = createMockResponse(
        { data: 'test' },
        200,
        { 'x-custom-header': 'value' }
      )
      expect(response.headers['x-custom-header']).toBe('value')
    })
  })

  describe('createMockPaginatedResponse', () => {
    it('should create a paginated response', () => {
      const items = [{ id: '1' }, { id: '2' }]
      const response = createMockPaginatedResponse(items, 1, 10, 2)
      expect(response.results).toEqual(items)
      expect(response.count).toBe(2)
      expect(response.next).toBeNull()
      expect(response.previous).toBeNull()
    })

    it('should create a paginated response with next page', () => {
      const items = [{ id: '1' }, { id: '2' }]
      const response = createMockPaginatedResponse(items, 1, 2, 10)
      expect(response.next).toBe('?page=2')
    })
  })

  describe('createMockError', () => {
    it('should create a mock error', () => {
      const error = createMockError('Not found', 404)
      expect(error.message).toBe('Not found')
      expect(error.response?.status).toBe(404)
      expect(error.isAxiosError).toBe(true)
    })

    it('should create a mock error with custom data', () => {
      const errorData = { error: { message: 'Custom error', code: 'CUSTOM' } }
      const error = createMockError('Error', 400, errorData)
      expect(error.response?.data).toEqual(errorData)
    })
  })

  describe('createMockNetworkError', () => {
    it('should create a network error without response', () => {
      const error = createMockNetworkError('Network error')
      expect(error.message).toBe('Network error')
      expect(error.response).toBeUndefined()
      expect(error.isAxiosError).toBe(true)
    })
  })

  describe('createMockApiErrorResponse', () => {
    it('should create an API error response', () => {
      const response = createMockApiErrorResponse(
        'Validation failed',
        'VALIDATION_ERROR',
        400
      )
      expect(response.error.message).toBe('Validation failed')
      expect(response.error.code).toBe('VALIDATION_ERROR')
      expect(response.error.request_id).toBeDefined()
    })
  })
})

describe('test data factories', () => {
  beforeEach(() => {
    resetIdCounter()
  })

  describe('createTestAsset', () => {
    it('should create a test asset', () => {
      const asset = createTestAsset()
      expect(asset.id).toBeDefined()
      expect(asset.name).toBeDefined()
      expect(asset.status).toBe('ACTIVE')
    })

    it('should create a test asset with overrides', () => {
      const asset = createTestAsset({
        overrides: { name: 'Custom Asset', status: 'DRAFT' },
      })
      expect(asset.name).toBe('Custom Asset')
      expect(asset.status).toBe('DRAFT')
    })

    it('should create unique IDs by default', () => {
      const asset1 = createTestAsset()
      const asset2 = createTestAsset()
      expect(asset1.id).not.toBe(asset2.id)
    })
  })

  describe('createTestAssets', () => {
    it('should create multiple test assets', () => {
      const assets = createTestAssets(3)
      expect(assets).toHaveLength(3)
      expect(assets[0].id).not.toBe(assets[1].id)
    })
  })

  describe('createTestContract', () => {
    it('should create a test contract', () => {
      const contract = createTestContract()
      expect(contract.id).toBeDefined()
      expect(contract.hub_contract_json).toBeDefined()
      expect(contract.status).toBe('ACTIVE')
    })
  })

  describe('createTestContracts', () => {
    it('should create multiple test contracts', () => {
      const contracts = createTestContracts(3)
      expect(contracts).toHaveLength(3)
    })
  })

  describe('createTestJob', () => {
    it('should create a test job', () => {
      const job = createTestJob()
      expect(job.id).toBeDefined()
      expect(job.type).toBe('DQ_RUN')
      expect(job.status).toBe('COMPLETED')
    })
  })

  describe('createTestJobs', () => {
    it('should create multiple test jobs with varied types', () => {
      const jobs = createTestJobs(5)
      expect(jobs).toHaveLength(5)
      expect(jobs[0].type).not.toBe(jobs[1].type)
    })
  })

  describe('createTestDataset', () => {
    it('should create a test dataset', () => {
      const dataset = createTestDataset()
      expect(dataset.id).toBeDefined()
      expect(dataset.format).toBe('CSV')
      expect(dataset.schema_json).toBeDefined()
    })
  })

  describe('createTestDatasets', () => {
    it('should create multiple test datasets with varied formats', () => {
      const datasets = createTestDatasets(3)
      expect(datasets).toHaveLength(3)
      expect(datasets[0].format).not.toBe(datasets[1].format)
    })
  })

  describe('createTestUser', () => {
    it('should create a test user', () => {
      const user = createTestUser()
      expect(user.id).toBeDefined()
      expect(user.email).toBeDefined()
      expect(user.username).toBeDefined()
    })
  })

  describe('createTestTenant', () => {
    it('should create a test tenant', () => {
      const tenant = createTestTenant()
      expect(tenant.id).toBeDefined()
      expect(tenant.name).toBeDefined()
      expect(tenant.slug).toBeDefined()
    })
  })
})

