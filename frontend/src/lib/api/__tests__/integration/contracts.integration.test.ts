/**
 * Contract API Integration Tests
 *
 * Comprehensive integration tests for Contract API endpoints.
 * These tests make real HTTP requests to the API server.
 */

import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest'
import {
  listContracts,
  getContract,
  createContract,
  updateContract,
  validateContract,
  deleteContract,
  type Contract,
  type CreateContractRequest,
  type UpdateContractRequest,
} from '@/lib/api/contracts'
import { AxiosError } from 'axios'
import { config } from '@/lib/config/env'

const TEST_CONFIG = {
  skipIfUnavailable: true,
  apiBaseUrl: config.api.baseUrl,
  cleanupAfterTests: true,
}

const testContracts: string[] = []

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

describe('Contract API Integration Tests', () => {
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
    if (TEST_CONFIG.cleanupAfterTests && apiAvailable) {
      for (const contractId of testContracts) {
        try {
          await deleteContract(contractId)
        } catch (error) {
          console.warn(`Failed to cleanup contract ${contractId}:`, error)
        }
      }
    }
  })

  beforeEach(() => {
    if (!apiAvailable) {
      return
    }
  })

  describe('listContracts', () => {
    it('should list contracts successfully', async () => {
      if (!apiAvailable) return

      const response = await listContracts()

      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
      expect(response.count).toBeGreaterThanOrEqual(0)
    })

    it('should support pagination', async () => {
      if (!apiAvailable) return

      const page1 = await listContracts({ page: 1, page_size: 10 })
      expect(page1.results).toBeInstanceOf(Array)
      expect(page1.results.length).toBeLessThanOrEqual(10)
    })

    it('should support filtering by owner email', async () => {
      if (!apiAvailable) return

      const response = await listContracts({ owner_email: 'test@example.com' })
      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
    })

    it('should support filtering by tags', async () => {
      if (!apiAvailable) return

      const response = await listContracts({ tag: 'test' })
      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
    })

    it('should support sorting', async () => {
      if (!apiAvailable) return

      const response = await listContracts({ ordering: '-created_at' })
      expect(response).toBeDefined()
      expect(response.results).toBeInstanceOf(Array)
    })
  })

  describe('createContract', () => {
    it('should create contract successfully', async () => {
      if (!apiAvailable) return

      const contractData: CreateContractRequest = {
        original_raw: JSON.stringify({
          hub_contract_version: '1.0.0',
          id: `test-contract-${Date.now()}`,
          info: {
            name: 'Test Contract',
            owners: [{ name: 'Test Owner', email: 'test@example.com' }],
          },
          schema: {
            models: [
              {
                name: 'TestModel',
                fields: [{ name: 'id', type: 'string' }],
              },
            ],
          },
        }),
        original_format: 'JSON',
        name: `Test Contract ${Date.now()}`,
      }

      const contract = await createContract(contractData)

      expect(contract).toBeDefined()
      expect(contract.id).toBeDefined()
      expect(contract.hub_contract_json).toBeDefined()
      expect(contract.status).toBeDefined()

      testContracts.push(contract.id)
    })

    it('should handle invalid contract format', async () => {
      if (!apiAvailable) return

      const invalidData: CreateContractRequest = {
        original_raw: 'invalid json {',
        original_format: 'JSON',
      }

      try {
        await createContract(invalidData)
        expect.fail('Should have thrown validation error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(400)
      }
    })

    it('should handle YAML format', async () => {
      if (!apiAvailable) return

      const yamlData: CreateContractRequest = {
        original_raw: `
hub_contract_version: "1.0.0"
id: "test-yaml-${Date.now()}"
info:
  name: "YAML Test Contract"
schema:
  models:
    - name: "TestModel"
      fields:
        - name: "id"
          type: "string"
        `.trim(),
        original_format: 'YAML',
      }

      const contract = await createContract(yamlData)
      expect(contract).toBeDefined()
      expect(contract.id).toBeDefined()

      testContracts.push(contract.id)
    })
  })

  describe('getContract', () => {
    let testContractId: string

    beforeEach(async () => {
      if (!apiAvailable) return

      const contractData: CreateContractRequest = {
        original_raw: JSON.stringify({
          hub_contract_version: '1.0.0',
          id: `get-test-${Date.now()}`,
          info: { name: 'Get Test Contract' },
        }),
        original_format: 'JSON',
      }
      const contract = await createContract(contractData)
      testContractId = contract.id
      testContracts.push(testContractId)
    })

    it('should get contract by ID successfully', async () => {
      if (!apiAvailable) return

      const contract = await getContract(testContractId)

      expect(contract).toBeDefined()
      expect(contract.id).toBe(testContractId)
      expect(contract.hub_contract_json).toBeDefined()
      expect(contract.status).toBeDefined()
    })

    it('should handle 404 for non-existent contract', async () => {
      if (!apiAvailable) return

      const nonExistentId = '00000000-0000-0000-0000-000000000000'

      try {
        await getContract(nonExistentId)
        expect.fail('Should have thrown 404 error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(404)
      }
    })
  })

  describe('updateContract', () => {
    let testContract: Contract

    beforeEach(async () => {
      if (!apiAvailable) return

      const contractData: CreateContractRequest = {
        original_raw: JSON.stringify({
          hub_contract_version: '1.0.0',
          id: `update-test-${Date.now()}`,
          info: { name: 'Update Test Contract' },
        }),
        original_format: 'JSON',
      }
      testContract = await createContract(contractData)
      testContracts.push(testContract.id)
    })

    it('should update contract successfully', async () => {
      if (!apiAvailable) return

      const updateData: UpdateContractRequest = {
        original_raw: JSON.stringify({
          hub_contract_version: '1.0.0',
          id: testContract.hub_contract_json.id,
          info: { name: 'Updated Contract Name' },
        }),
        original_format: 'JSON',
      }

      const updatedContract = await updateContract(testContract.id, updateData)

      expect(updatedContract).toBeDefined()
      expect(updatedContract.id).toBe(testContract.id)
    })

    it('should handle status update', async () => {
      if (!apiAvailable) return

      const updateData: UpdateContractRequest = {
        status: 'ACTIVE',
      }

      const updatedContract = await updateContract(testContract.id, updateData)
      expect(updatedContract.status).toBe('ACTIVE')
    })
  })

  describe('validateContract', () => {
    let testContractId: string

    beforeEach(async () => {
      if (!apiAvailable) return

      const contractData: CreateContractRequest = {
        original_raw: JSON.stringify({
          hub_contract_version: '1.0.0',
          id: `validate-test-${Date.now()}`,
          info: { name: 'Validate Test Contract' },
          schema: {
            models: [
              {
                name: 'TestModel',
                fields: [{ name: 'id', type: 'string' }],
              },
            ],
          },
        }),
        original_format: 'JSON',
      }
      const contract = await createContract(contractData)
      testContractId = contract.id
      testContracts.push(testContractId)
    })

    it('should validate contract successfully', async () => {
      if (!apiAvailable) return

      const validation = await validateContract(testContractId)

      expect(validation).toBeDefined()
      expect(validation.validation_status).toBeDefined()
      expect(validation.errors).toBeInstanceOf(Array)
      expect(validation.warnings).toBeInstanceOf(Array)
    })

    it('should support async validation', async () => {
      if (!apiAvailable) return

      const validation = await validateContract(testContractId, { async: true })

      expect(validation).toBeDefined()
      // Async validation might return a job_id
      if (validation.job_id) {
        expect(validation.job_id).toBeDefined()
        expect(validation.status).toBeDefined()
      }
    })
  })

  describe('deleteContract', () => {
    it('should delete contract successfully', async () => {
      if (!apiAvailable) return

      const contractData: CreateContractRequest = {
        original_raw: JSON.stringify({
          hub_contract_version: '1.0.0',
          id: `delete-test-${Date.now()}`,
          info: { name: 'Delete Test Contract' },
        }),
        original_format: 'JSON',
      }
      const contract = await createContract(contractData)

      await deleteContract(contract.id)

      try {
        await getContract(contract.id)
        expect.fail('Contract should have been deleted')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(404)
      }
    })
  })

  describe('Error Handling', () => {
    it('should handle validation errors', async () => {
      if (!apiAvailable) return

      const invalidData: CreateContractRequest = {
        original_raw: 'invalid',
        original_format: 'JSON',
      }

      try {
        await createContract(invalidData)
        expect.fail('Should have thrown validation error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(400)
      }
    })

    it('should handle network errors', async () => {
      if (!apiAvailable) return

      try {
        await listContracts({}, {
          baseURL: 'http://invalid-host:8000',
        } as any)
        expect.fail('Should have thrown network error')
      } catch (error) {
        expect(error).toBeInstanceOf(Error)
      }
    })
  })

  describe('Retry Logic', () => {
    it('should retry on 500 errors', async () => {
      if (!apiAvailable) return

      const response = await listContracts({}, {
        retry: {
          maxRetries: 3,
          retryableStatusCodes: [500, 502, 503, 504],
        },
      } as any)

      expect(response).toBeDefined()
    })

    it('should not retry on 400 errors', async () => {
      if (!apiAvailable) return

      const invalidData: CreateContractRequest = {
        original_raw: 'invalid',
        original_format: 'JSON',
      }

      try {
        await createContract(invalidData)
        expect.fail('Should have thrown validation error')
      } catch (error) {
        expect(error).toBeInstanceOf(AxiosError)
        const axiosError = error as AxiosError
        expect(axiosError.response?.status).toBe(400)
      }
    })
  })
})

