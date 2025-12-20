/**
 * MSW Handlers
 *
 * Mock Service Worker handlers for API endpoints.
 * Provides default mock handlers for all API endpoints.
 */

import { http, HttpResponse, delay } from 'msw'
import { config } from '@/lib/config'
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
} from '../mocks/data'

/**
 * Base API URL
 */
const API_BASE_URL = config.api.baseUrl

/**
 * Helper to create paginated response
 */
function createPaginatedResponse<T>(
  items: T[],
  page: number = 1,
  pageSize: number = 50
) {
  const start = (page - 1) * pageSize
  const end = start + pageSize
  const paginatedItems = items.slice(start, end)

  return HttpResponse.json({
    count: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(items.length / pageSize),
    has_next: end < items.length,
    has_previous: page > 1,
    next_page: end < items.length ? page + 1 : null,
    previous_page: page > 1 ? page - 1 : null,
    results: paginatedItems,
  })
}

/**
 * Helper to create error response
 */
function createErrorResponse(
  message: string,
  code: string,
  status: number = 400,
  details?: Record<string, any>
) {
  return HttpResponse.json(
    {
      error: {
        message,
        code,
        http_status: status,
        request_id: `test-request-${Date.now()}`,
        timestamp: new Date().toISOString(),
        details,
      },
    },
    { status }
  )
}

/**
 * Mock data stores (in-memory)
 */
const mockData = {
  assets: createTestAssets(50),
  contracts: createTestContracts(50),
  jobs: createTestJobs(50),
  datasets: createTestDatasets(50),
  users: Array.from({ length: 20 }, () => createTestUser()),
  tenants: Array.from({ length: 5 }, () => createTestTenant()),
}

/**
 * Authentication handlers
 */
export const authHandlers = [
  // Login
  http.post(`${API_BASE_URL}/auth/login/`, async ({ request }) => {
    const body = await request.json().catch(() => ({})) as { username?: string; password?: string }

    if (body.username === 'test' && body.password === 'test') {
      return HttpResponse.json({
        access: 'mock-access-token',
        refresh: 'mock-refresh-token',
        user: createTestUser({ username: 'test' }),
      })
    }

    return createErrorResponse('Invalid credentials', 'AUTHENTICATION_ERROR', 401)
  }),

  // Logout
  http.post(`${API_BASE_URL}/auth/logout/`, () => {
    return HttpResponse.json({ success: true })
  }),

  // Refresh token
  http.post(`${API_BASE_URL}/auth/refresh/`, () => {
    return HttpResponse.json({
      access: 'mock-access-token-refreshed',
    })
  }),

  // Get current user
  http.get(`${API_BASE_URL}/auth/me/`, () => {
    return HttpResponse.json(createTestUser({ username: 'test' }))
  }),
]

/**
 * Assets handlers
 */
export const assetsHandlers = [
  // List assets
  http.get(`${API_BASE_URL}/assets/`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const pageSize = parseInt(url.searchParams.get('page_size') || '50', 10)
    const search = url.searchParams.get('search')
    const status = url.searchParams.get('status')

    let filteredAssets = [...mockData.assets]

    if (search) {
      filteredAssets = filteredAssets.filter(
        (asset) =>
          asset.name.toLowerCase().includes(search.toLowerCase()) ||
          asset.description?.toLowerCase().includes(search.toLowerCase())
      )
    }

    if (status) {
      filteredAssets = filteredAssets.filter((asset) => asset.status === status)
    }

    return createPaginatedResponse(filteredAssets, page, pageSize)
  }),

  // Get asset by ID
  http.get(`${API_BASE_URL}/assets/:id/`, ({ params }) => {
    const asset = mockData.assets.find((a) => a.id === params.id as string)

    if (!asset) {
      return createErrorResponse('Asset not found', 'NOT_FOUND', 404)
    }

    return HttpResponse.json(asset)
  }),

  // Create asset
  http.post(`${API_BASE_URL}/assets/`, async ({ request }) => {
    const body = await request.json() as Partial<typeof mockData.assets[0]>
    const newAsset = createTestAsset({
      overrides: {
        ...body,
        id: `asset-${Date.now()}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    })

    mockData.assets.push(newAsset)
    return HttpResponse.json(newAsset, { status: 201 })
  }),

  // Update asset
  http.put(`${API_BASE_URL}/assets/:id/`, async ({ params, request }) => {
    const assetIndex = mockData.assets.findIndex((a) => a.id === params.id as string)

    if (assetIndex === -1) {
      return createErrorResponse('Asset not found', 'NOT_FOUND', 404)
    }

    const body = await request.json() as Partial<typeof mockData.assets[0]>
    const updatedAsset = {
      ...mockData.assets[assetIndex],
      ...body,
      updated_at: new Date().toISOString(),
    }

    mockData.assets[assetIndex] = updatedAsset
    return HttpResponse.json(updatedAsset)
  }),

  // Delete asset
  http.delete(`${API_BASE_URL}/assets/:id/`, ({ params }) => {
    const assetIndex = mockData.assets.findIndex((a) => a.id === params.id as string)

    if (assetIndex === -1) {
      return createErrorResponse('Asset not found', 'NOT_FOUND', 404)
    }

    mockData.assets.splice(assetIndex, 1)
    return new HttpResponse(null, { status: 204 })
  }),
]

/**
 * Contracts handlers
 */
export const contractsHandlers = [
  // List contracts
  http.get(`${API_BASE_URL}/api/v1/contracts/`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const pageSize = parseInt(url.searchParams.get('page_size') || '50', 10)
    const search = url.searchParams.get('search')
    const ownerName = url.searchParams.get('owner_name')
    const ownerEmail = url.searchParams.get('owner_email')
    const tag = url.searchParams.get('tag')
    const complianceRegime = url.searchParams.get('compliance_regime')
    const qualityProfile = url.searchParams.get('quality_profile')
    const status = url.searchParams.get('status')
    const ordering = url.searchParams.get('ordering') || '-created_at'

    let filteredContracts = [...mockData.contracts]

    // Apply search filter
    if (search) {
      filteredContracts = filteredContracts.filter((contract) =>
        contract.hub_contract_json?.info?.name?.toLowerCase().includes(search.toLowerCase())
      )
    }

    // Apply owner name filter (case-insensitive partial match)
    if (ownerName) {
      filteredContracts = filteredContracts.filter((contract) => {
        // Check both hub_contract_json.info.owners and top-level owners
        const owners = contract.hub_contract_json?.info?.owners || contract.owners || []
        return owners.some((owner: any) =>
          owner.name?.toLowerCase().includes(ownerName.toLowerCase())
        )
      })
    }

    // Apply owner email filter (case-insensitive)
    if (ownerEmail) {
      filteredContracts = filteredContracts.filter((contract) => {
        // Check both hub_contract_json.info.owners and top-level owners
        const owners = contract.hub_contract_json?.info?.owners || contract.owners || []
        return owners.some((owner: any) =>
          owner.email?.toLowerCase() === ownerEmail.toLowerCase()
        )
      })
    }

    // Apply tag filter
    if (tag) {
      filteredContracts = filteredContracts.filter((contract) => {
        const tags = contract.hub_contract_json?.info?.tags || []
        return Array.isArray(tags) ? tags.includes(tag) : tags === tag
      })
    }

    // Apply compliance regime filter
    if (complianceRegime) {
      filteredContracts = filteredContracts.filter((contract) => {
        const regimes = contract.hub_contract_json?.info?.compliance_regimes || []
        return Array.isArray(regimes) ? regimes.includes(complianceRegime) : regimes === complianceRegime
      })
    }

    // Apply quality profile filter
    if (qualityProfile) {
      filteredContracts = filteredContracts.filter((contract) => {
        return contract.quality_profile_key === qualityProfile
      })
    }

    // Apply status filter
    if (status) {
      filteredContracts = filteredContracts.filter((contract) => {
        return contract.status === status
      })
    }

    // Apply sorting
    if (ordering) {
      const isDesc = ordering.startsWith('-')
      const sortField = isDesc ? ordering.slice(1) : ordering

      filteredContracts.sort((a, b) => {
        let aValue: any
        let bValue: any

        if (sortField === 'created_at') {
          aValue = new Date(a.created_at).getTime()
          bValue = new Date(b.created_at).getTime()
        } else if (sortField === 'name') {
          aValue = a.hub_contract_json?.info?.name || ''
          bValue = b.hub_contract_json?.info?.name || ''
        } else if (sortField === 'status') {
          aValue = a.status || ''
          bValue = b.status || ''
        } else {
          aValue = (a as any)[sortField] || ''
          bValue = (b as any)[sortField] || ''
        }

        if (aValue < bValue) return isDesc ? 1 : -1
        if (aValue > bValue) return isDesc ? -1 : 1
        return 0
      })
    }

    return createPaginatedResponse(filteredContracts, page, pageSize)
  }),

  // Get contract by ID
  http.get(`${API_BASE_URL}/api/v1/contracts/:id/`, ({ params }) => {
    const contract = mockData.contracts.find((c) => c.id === params.id as string)

    if (!contract) {
      return createErrorResponse('Contract not found', 'NOT_FOUND', 404)
    }

    return HttpResponse.json(contract)
  }),

  // Create contract
  http.post(`${API_BASE_URL}/api/v1/contracts/`, async ({ request }) => {
    const body = await request.json() as Partial<typeof mockData.contracts[0]>
    const newContract = createTestContract({
      overrides: {
        ...body,
        id: `contract-${Date.now()}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    })

    mockData.contracts.push(newContract)
    return HttpResponse.json(newContract, { status: 201 })
  }),

  // Update contract
  http.put(`${API_BASE_URL}/api/v1/contracts/:id/`, async ({ params, request }) => {
    const contractIndex = mockData.contracts.findIndex((c) => c.id === params.id as string)

    if (contractIndex === -1) {
      return createErrorResponse('Contract not found', 'NOT_FOUND', 404)
    }

    const body = await request.json() as Partial<typeof mockData.contracts[0]>
    const updatedContract = {
      ...mockData.contracts[contractIndex],
      ...body,
      updated_at: new Date().toISOString(),
    }

    mockData.contracts[contractIndex] = updatedContract
    return HttpResponse.json(updatedContract)
  }),

  // Delete contract
  http.delete(`${API_BASE_URL}/api/v1/contracts/:id/`, ({ params }) => {
    const contractIndex = mockData.contracts.findIndex((c) => c.id === params.id as string)

    if (contractIndex === -1) {
      return createErrorResponse('Contract not found', 'NOT_FOUND', 404)
    }

    mockData.contracts.splice(contractIndex, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  // Validate contract
  http.post(`${API_BASE_URL}/api/v1/contracts/:id/validate/`, ({ params }) => {
    const contract = mockData.contracts.find((c) => c.id === params.id as string)

    if (!contract) {
      return createErrorResponse('Contract not found', 'NOT_FOUND', 404)
    }

    return HttpResponse.json({
      valid: true,
      errors: [],
      warnings: [],
    })
  }),
]

/**
 * Jobs handlers
 */
export const jobsHandlers = [
  // List jobs
  http.get(`${API_BASE_URL}/jobs/`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const pageSize = parseInt(url.searchParams.get('page_size') || '50', 10)

    return createPaginatedResponse(mockData.jobs, page, pageSize)
  }),

  // Get job by ID
  http.get(`${API_BASE_URL}/jobs/:id/`, ({ params }) => {
    const job = mockData.jobs.find((j) => j.id === params.id as string)

    if (!job) {
      return createErrorResponse('Job not found', 'NOT_FOUND', 404)
    }

    return HttpResponse.json(job)
  }),

  // Create job
  http.post(`${API_BASE_URL}/jobs/`, async ({ request }) => {
    const body = await request.json() as Partial<typeof mockData.jobs[0]>
    const newJob = createTestJob({
      overrides: {
        ...body,
        id: `job-${Date.now()}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    })

    mockData.jobs.push(newJob)
    return HttpResponse.json(newJob, { status: 201 })
  }),

  // Cancel job
  http.post(`${API_BASE_URL}/jobs/:id/cancel/`, ({ params }) => {
    const job = mockData.jobs.find((j) => j.id === params.id as string)

    if (!job) {
      return createErrorResponse('Job not found', 'NOT_FOUND', 404)
    }

    const updatedJob = {
      ...job,
      status: 'CANCELLED' as const,
      updated_at: new Date().toISOString(),
    }

    const jobIndex = mockData.jobs.findIndex((j) => j.id === params.id as string)
    mockData.jobs[jobIndex] = updatedJob

    return HttpResponse.json(updatedJob)
  }),
]

/**
 * Datasets handlers
 */
export const datasetsHandlers = [
  // List datasets
  http.get(`${API_BASE_URL}/datasets/`, ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1', 10)
    const pageSize = parseInt(url.searchParams.get('page_size') || '50', 10)

    return createPaginatedResponse(mockData.datasets, page, pageSize)
  }),

  // Get dataset by ID
  http.get(`${API_BASE_URL}/datasets/:id/`, ({ params }) => {
    const dataset = mockData.datasets.find((d) => d.id === params.id as string)

    if (!dataset) {
      return createErrorResponse('Dataset not found', 'NOT_FOUND', 404)
    }

    return HttpResponse.json(dataset)
  }),

  // Create dataset
  http.post(`${API_BASE_URL}/datasets/`, async ({ request }) => {
    const body = await request.json() as Partial<typeof mockData.datasets[0]>
    const newDataset = createTestDataset({
      overrides: {
        ...body,
        id: `dataset-${Date.now()}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    })

    mockData.datasets.push(newDataset)
    return HttpResponse.json(newDataset, { status: 201 })
  }),

  // Update dataset
  http.put(`${API_BASE_URL}/datasets/:id/`, async ({ params, request }) => {
    const datasetIndex = mockData.datasets.findIndex((d) => d.id === params.id as string)

    if (datasetIndex === -1) {
      return createErrorResponse('Dataset not found', 'NOT_FOUND', 404)
    }

    const body = await request.json() as Partial<typeof mockData.datasets[0]>
    const updatedDataset = {
      ...mockData.datasets[datasetIndex],
      ...body,
      updated_at: new Date().toISOString(),
    }

    mockData.datasets[datasetIndex] = updatedDataset
    return HttpResponse.json(updatedDataset)
  }),

  // Delete dataset
  http.delete(`${API_BASE_URL}/datasets/:id/`, ({ params }) => {
    const datasetIndex = mockData.datasets.findIndex((d) => d.id === params.id as string)

    if (datasetIndex === -1) {
      return createErrorResponse('Dataset not found', 'NOT_FOUND', 404)
    }

    mockData.datasets.splice(datasetIndex, 1)
    return new HttpResponse(null, { status: 204 })
  }),
]

/**
 * API info handler
 */
export const apiInfoHandler = [
  http.get(`${API_BASE_URL}/`, () => {
    return HttpResponse.json({
      name: 'Interoperable Data Hub API',
      version: '1.0.0',
      base_url: API_BASE_URL,
      documentation: {
        openapi: '/api-docs/openapi.json',
        openapi_yaml: `${API_BASE_URL}/openapi.yaml`,
        swagger: '/api-docs/',
        redoc: '/api-docs/redoc/',
      },
      endpoints: {
        auth: `${API_BASE_URL}/auth/`,
        tenants: `${API_BASE_URL}/tenants/`,
        users: `${API_BASE_URL}/users/`,
        files: `${API_BASE_URL}/files/`,
        datasets: `${API_BASE_URL}/datasets/`,
        assets: `${API_BASE_URL}/assets/`,
        contracts: `${API_BASE_URL}/contracts/`,
        jobs: `${API_BASE_URL}/jobs/`,
        dq: `${API_BASE_URL}/dq/`,
        compliance: `${API_BASE_URL}/compliance/`,
        semantic: `${API_BASE_URL}/semantic/`,
        marketplace: `${API_BASE_URL}/marketplace/`,
        audit: `${API_BASE_URL}/audit/`,
        webhooks: `${API_BASE_URL}/webhooks/`,
        analytics: `${API_BASE_URL}/analytics/`,
      },
    })
  }),
]

/**
 * Default handlers (all handlers combined)
 */
export const defaultHandlers = [
  ...apiInfoHandler,
  ...authHandlers,
  ...assetsHandlers,
  ...contractsHandlers,
  ...jobsHandlers,
  ...datasetsHandlers,
]

/**
 * Reset mock data (useful for test cleanup)
 */
export function resetMockData() {
  mockData.assets = createTestAssets(50)
  mockData.contracts = createTestContracts(50)
  mockData.jobs = createTestJobs(50)
  mockData.datasets = createTestDatasets(50)
  mockData.users = Array.from({ length: 20 }, () => createTestUser())
  mockData.tenants = Array.from({ length: 5 }, () => createTestTenant())
}

/**
 * Get mock data (for test utilities)
 */
export function getMockData() {
  return mockData
}

