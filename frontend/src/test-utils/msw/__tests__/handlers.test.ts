/**
 * MSW Handlers Tests
 *
 * Tests for MSW handlers to ensure they work correctly.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { server } from '../server'
import { http, HttpResponse } from 'msw'
import { config } from '@/lib/config'
import { resetMockData } from '../handlers'

const API_BASE_URL = config.api.baseUrl

describe('MSW Handlers', () => {
  beforeEach(() => {
    resetMockData()
  })

  describe('Assets handlers', () => {
    it('should return paginated list of assets', async () => {
      const response = await fetch(`${API_BASE_URL}/assets/`)
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('count')
      expect(data).toHaveProperty('results')
      expect(data).toHaveProperty('page')
      expect(data).toHaveProperty('page_size')
      expect(Array.isArray(data.results)).toBe(true)
    })

    it('should return asset by ID', async () => {
      // First get list to get an ID
      const listResponse = await fetch(`${API_BASE_URL}/assets/`)
      const listData = await listResponse.json()
      const assetId = listData.results[0].id

      const response = await fetch(`${API_BASE_URL}/assets/${assetId}/`)
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('id', assetId)
    })

    it('should return 404 for non-existent asset', async () => {
      const response = await fetch(`${API_BASE_URL}/assets/non-existent-id/`)
      const data = await response.json()

      expect(response.status).toBe(404)
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code', 'NOT_FOUND')
    })

    it('should create new asset', async () => {
      const newAsset = {
        name: 'New Test Asset',
        description: 'Test description',
        domain: 'test-domain',
      }

      const response = await fetch(`${API_BASE_URL}/assets/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newAsset),
      })

      const data = await response.json()

      expect(response.status).toBe(201)
      expect(data).toHaveProperty('id')
      expect(data).toHaveProperty('name', newAsset.name)
    })
  })

  describe('Contracts handlers', () => {
    it('should return paginated list of contracts', async () => {
      const response = await fetch(`${API_BASE_URL}/contracts/`)
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('count')
      expect(data).toHaveProperty('results')
      expect(Array.isArray(data.results)).toBe(true)
    })

    it('should return contract by ID', async () => {
      const listResponse = await fetch(`${API_BASE_URL}/contracts/`)
      const listData = await listResponse.json()
      const contractId = listData.results[0].id

      const response = await fetch(`${API_BASE_URL}/contracts/${contractId}/`)
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('id', contractId)
    })

    it('should validate contract', async () => {
      const listResponse = await fetch(`${API_BASE_URL}/contracts/`)
      const listData = await listResponse.json()
      const contractId = listData.results[0].id

      const response = await fetch(`${API_BASE_URL}/contracts/${contractId}/validate/`, {
        method: 'POST',
      })

      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('valid', true)
    })
  })

  describe('Auth handlers', () => {
    it('should login with valid credentials', async () => {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: 'test',
          password: 'test',
        }),
      })

      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('access')
      expect(data).toHaveProperty('refresh')
      expect(data).toHaveProperty('user')
    })

    it('should reject invalid credentials', async () => {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: 'invalid',
          password: 'invalid',
        }),
      })

      const data = await response.json()

      expect(response.status).toBe(401)
      expect(data).toHaveProperty('error')
      expect(data.error).toHaveProperty('code', 'AUTHENTICATION_ERROR')
    })

    it('should get current user', async () => {
      const response = await fetch(`${API_BASE_URL}/auth/me/`)
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('id')
      expect(data).toHaveProperty('username')
    })
  })

  describe('API info handler', () => {
    it('should return API info', async () => {
      const response = await fetch(`${API_BASE_URL}/`)
      const data = await response.json()

      expect(response.status).toBe(200)
      expect(data).toHaveProperty('name')
      expect(data).toHaveProperty('version')
      expect(data).toHaveProperty('endpoints')
    })
  })
})

