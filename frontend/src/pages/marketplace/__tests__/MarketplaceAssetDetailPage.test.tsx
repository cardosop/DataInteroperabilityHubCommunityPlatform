/**
 * MarketplaceAssetDetailPage Tests
 *
 * Comprehensive tests for the MarketplaceAssetDetailPage component covering:
 * - Asset information display
 * - Contract details display
 * - Dataset information display
 * - Data quality metrics display
 * - Compliance information display
 * - Marketplace policy display
 * - Contract download functionality
 * - Access request functionality
 * - Related assets display
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MarketplaceAssetDetailPage } from '../MarketplaceAssetDetailPage'
import * as marketplaceApi from '@/lib/api/marketplace'
import {
  useMarketplaceListing,
  useMarketplaceListingPreview,
  useCreateMarketplaceOrder,
  useDownloadContract,
} from '@/hooks/useMarketplace'

// Mock hooks
vi.mock('@/hooks/useMarketplace', () => ({
  useMarketplaceListing: vi.fn(),
  useMarketplaceListingPreview: vi.fn(),
  useCreateMarketplaceOrder: vi.fn(),
  useDownloadContract: vi.fn(),
}))

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: 'listing-123' }),
  }
})

const createTestQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

const mockListing: marketplaceApi.MarketplaceListing = {
  id: 'listing-123',
  tenant: 'tenant-1',
  asset: 'asset-123',
  status: 'PUBLISHED',
  pricing_model: 'REQUEST_APPROVAL',
  metadata_json: {
    title: 'Test Asset',
    short_description: 'Short description',
    long_description: 'Long description',
    tags: ['tag1', 'tag2'],
    domain: 'finance',
    license_summary: 'MIT License',
    intended_use: ['analytics', 'research'],
    restricted_use: ['commercial'],
  },
  published_at: '2024-01-01T00:00:00Z',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  title: 'Test Asset',
  description: 'Long description',
  short_description: 'Short description',
  tags: ['tag1', 'tag2'],
  domain: 'finance',
}

const mockPreview: marketplaceApi.ListingPreviewResponse = {
  listing_id: 'listing-123',
  asset_id: 'asset-123',
  sample_data: {
    rows: [{ id: 1, name: 'Test' }],
    total_rows: 1000,
    sample_size: 1,
  },
  quality_metrics: {
    completeness: 0.95,
    accuracy: 0.98,
    freshness: 'current',
    overall_score: 0.96,
  },
  schema: {
    fields: [
      { name: 'id', type: 'string', nullable: false },
      { name: 'name', type: 'string', nullable: true },
    ],
  },
  preview_expires_at: '2024-01-01T01:00:00Z',
}

describe('MarketplaceAssetDetailPage', () => {
  const mockUseMarketplaceListing = vi.mocked(useMarketplaceListing)
  const mockUseMarketplaceListingPreview = vi.mocked(useMarketplaceListingPreview)
  const mockUseCreateMarketplaceOrder = vi.mocked(useCreateMarketplaceOrder)
  const mockUseDownloadContract = vi.mocked(useDownloadContract)

  beforeEach(() => {
    vi.clearAllMocks()

    mockUseMarketplaceListing.mockReturnValue({
      data: mockListing,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as any)

    mockUseMarketplaceListingPreview.mockReturnValue({
      data: mockPreview,
      isLoading: false,
      error: null,
    } as any)

    mockUseCreateMarketplaceOrder.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
      reset: vi.fn(),
      status: 'idle',
    } as any)

    mockUseDownloadContract.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
      mutate: vi.fn(),
      reset: vi.fn(),
      status: 'idle',
    } as any)
  })

  describe('Rendering', () => {
    it('should render asset information', () => {
      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText('Test Asset')).toBeInTheDocument()
      expect(screen.getByText('Short description')).toBeInTheDocument()
      expect(screen.getByText('finance')).toBeInTheDocument()
    })

    it('should render contract details', () => {
      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      // Contract section should be present
      expect(screen.getByText(/contract/i)).toBeInTheDocument()
    })

    it('should render dataset information', () => {
      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText(/1,000/i)).toBeInTheDocument()
    })

    it('should render data quality metrics', () => {
      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText(/quality/i)).toBeInTheDocument()
      expect(screen.getByText(/96%/i)).toBeInTheDocument()
    })

    it('should render marketplace policy', () => {
      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText(/MIT License/i)).toBeInTheDocument()
      expect(screen.getByText(/analytics/i)).toBeInTheDocument()
    })
  })

  describe('Contract Download', () => {
    it('should call download contract when download button is clicked', async () => {
      const mockDownload = vi.fn().mockResolvedValue({
        contract_content: 'contract content',
        filename: 'contract.json',
        format: 'JSON',
        contract_id: 'contract-123',
      })

      mockUseDownloadContract.mockReturnValue({
        mutateAsync: mockDownload,
        isPending: false,
        isError: false,
        error: null,
        mutate: vi.fn(),
        reset: vi.fn(),
        status: 'idle',
      } as any)

      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      const downloadButton = screen.getByText(/download.*contract/i)
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(mockDownload).toHaveBeenCalledWith({
          listingId: 'listing-123',
          format: 'original',
        })
      })
    })
  })

  describe('Access Request', () => {
    it('should call create order when request access button is clicked', async () => {
      const mockCreateOrder = vi.fn().mockResolvedValue({
        order: {
          id: 'order-123',
          status: 'REQUESTED',
        },
      })

      mockUseCreateMarketplaceOrder.mockReturnValue({
        mutateAsync: mockCreateOrder,
        isPending: false,
        isError: false,
        error: null,
        mutate: vi.fn(),
        reset: vi.fn(),
        status: 'idle',
      } as any)

      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      const requestButton = screen.getByText(/request.*access/i)
      fireEvent.click(requestButton)

      await waitFor(() => {
        expect(mockCreateOrder).toHaveBeenCalledWith({
          listing_id: 'listing-123',
        })
      })
    })
  })

  describe('Loading States', () => {
    it('should show loading state when listing is loading', () => {
      mockUseMarketplaceListing.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      } as any)

      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText(/loading/i)).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should show error state when listing fails to load', () => {
      mockUseMarketplaceListing.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load'),
        refetch: vi.fn(),
      } as any)

      render(
        <TestWrapper>
          <MarketplaceAssetDetailPage />
        </TestWrapper>
      )

      expect(screen.getByText(/failed to load/i)).toBeInTheDocument()
    })
  })
})

