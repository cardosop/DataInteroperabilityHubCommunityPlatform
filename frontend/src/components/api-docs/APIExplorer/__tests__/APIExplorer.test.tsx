/**
 * APIExplorer Tests
 *
 * Comprehensive tests for the APIExplorer component covering:
 * - Endpoint selection
 * - Request parameter input
 * - API call execution
 * - Response display
 * - Error handling
 * - Loading states
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { APIExplorer } from '../APIExplorer'
import type { APIEndpoint } from '../../APIEndpointCard/types'
import { apiClient } from '@/lib/api/client'

const mockEndpoint: APIEndpoint = {
  method: 'GET',
  path: '/api/v1/assets/',
  description: 'List all assets',
  parameters: {
    query: [
      { name: 'page', type: 'integer', required: false, description: 'Page number' },
    ],
  },
  responses: [
    {
      status: 200,
      description: 'Success',
      example: { results: [] },
    },
  ],
}

// Mock API client
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))


describe('APIExplorer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render API explorer', () => {
      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      expect(screen.getByText(/api explorer/i)).toBeInTheDocument()
    })

    it('should display endpoint method and path', () => {
      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      expect(screen.getByText('GET')).toBeInTheDocument()
      expect(screen.getByText('/api/v1/assets/')).toBeInTheDocument()
    })

    it('should display send request button', () => {
      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      expect(screen.getByRole('button', { name: /send request/i })).toBeInTheDocument()
    })
  })

  describe('Request Parameters', () => {
    it('should display query parameters input', () => {
      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      expect(screen.getByLabelText(/page/i)).toBeInTheDocument()
    })

    it('should display body editor for POST requests', () => {
      const postEndpoint: APIEndpoint = {
        ...mockEndpoint,
        method: 'POST',
        parameters: {
          body: {
            schema: { name: 'string' },
            example: { name: 'Test' },
          },
        },
      }
      render(
        <TestWrapper>
          <APIExplorer endpoint={postEndpoint} baseUrl="http://localhost:8000" />
        </TestWrapper>
      )
      // Monaco editor should be present for body
      expect(screen.getByText(/request body/i)).toBeInTheDocument()
    })
  })

  describe('API Call Execution', () => {
    it('should make GET request when send button is clicked', async () => {
      const mockResponse = { data: { results: [] } }
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)

      const sendButton = screen.getByRole('button', { name: /send request/i })
      fireEvent.click(sendButton)

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/api/v1/assets/', expect.any(Object))
      })
    })

    it('should make POST request with body', async () => {
      const postEndpoint: APIEndpoint = {
        ...mockEndpoint,
        method: 'POST',
        parameters: {
          body: {
            schema: { name: 'string' },
            example: { name: 'Test Asset' },
          },
        },
      }
      const mockResponse = { data: { id: '123', name: 'Test Asset' } }
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse)

      render(
        <TestWrapper>
          <APIExplorer endpoint={postEndpoint} baseUrl="http://localhost:8000" />
        </TestWrapper>
      )

      const sendButton = screen.getByRole('button', { name: /send request/i })
      fireEvent.click(sendButton)

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith(
          '/api/v1/assets/',
          { name: 'Test Asset' },
          expect.any(Object)
        )
      })
    })

    it('should display response after successful request', async () => {
      const mockResponse = { data: { results: [{ id: '1', name: 'Asset 1' }] } }
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)

      const sendButton = screen.getByRole('button', { name: /send request/i })
      fireEvent.click(sendButton)

      await waitFor(() => {
        expect(screen.getByText(/response/i)).toBeInTheDocument()
      })
    })

    it('should display error message on failed request', async () => {
      const error = new Error('Request failed')
      vi.mocked(apiClient.get).mockRejectedValue(error)

      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)

      const sendButton = screen.getByRole('button', { name: /send request/i })
      fireEvent.click(sendButton)

      await waitFor(() => {
        expect(screen.getByText(/error/i)).toBeInTheDocument()
      })
    })
  })

  describe('Loading State', () => {
    it('should show loading state during request', async () => {
      let resolveRequest: (value: any) => void
      const promise = new Promise((resolve) => {
        resolveRequest = resolve
      })
      vi.mocked(apiClient.get).mockReturnValue(promise as any)

      renderWithProviders(<APIExplorer endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)

      const sendButton = screen.getByRole('button', { name: /send request/i })
      fireEvent.click(sendButton)

      await waitFor(() => {
        expect(screen.getByText(/loading/i)).toBeInTheDocument()
      })

      resolveRequest!({ data: {} })
    })
  })
})

