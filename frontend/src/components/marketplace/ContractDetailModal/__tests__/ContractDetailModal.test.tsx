/**
 * ContractDetailModal Tests
 *
 * Comprehensive tests for the ContractDetailModal component covering:
 * - Modal rendering and visibility
 * - Tab navigation
 * - Details tab content
 * - Preview tab content
 * - Download functionality
 * - Request access functionality
 * - Loading states
 * - Error handling
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ContractDetailModal } from '../../ContractDetailModal'
import type { MarketplaceListing } from '@/lib/api/marketplace'

// Mock hooks
const mockUseAsset = vi.fn()
const mockUseContract = vi.fn()
const mockUseDownloadContract = vi.fn()

vi.mock('@/hooks/useAssets', () => ({
  useAsset: () => mockUseAsset(),
}))

vi.mock('@/hooks/useContract', () => ({
  useContract: () => mockUseContract(),
}))

vi.mock('@/hooks/useMarketplace', () => ({
  useDownloadContract: () => mockUseDownloadContract(),
}))

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
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('ContractDetailModal', () => {
  const mockListing: MarketplaceListing = {
    id: 'listing-1',
    tenant: 'tenant-1',
    asset: 'asset-1',
    status: 'PUBLISHED',
    pricing_model: 'FREE',
    metadata_json: {
      title: 'Test Contract Listing',
      short_description: 'Short description',
      long_description: 'Long description',
      tags: ['analytics', 'customer'],
      domain: 'marketing',
    },
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    title: 'Test Contract Listing',
    short_description: 'Short description',
    description: 'Long description',
    tags: ['analytics', 'customer'],
    domain: 'marketing',
  }

  const mockAsset = {
    id: 'asset-1',
    contract_id: 'contract-1',
  }

  const mockContract = {
    id: 'contract-1',
    hub_contract_json: {
      hub_contract_version: '1',
      id: 'contract-1',
      info: {
        name: 'Test Contract',
        description: 'Contract description',
      },
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseAsset.mockReturnValue({
      data: mockAsset,
      isLoading: false,
    })
    mockUseContract.mockReturnValue({
      data: mockContract,
      isLoading: false,
      error: null,
    })
    mockUseDownloadContract.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
  })

  describe('Rendering', () => {
    it('should not render when open is false', () => {
      render(
        <TestWrapper>
          <ContractDetailModal
            open={false}
            listing={mockListing}
            onClose={vi.fn()}
          />
        </TestWrapper>
      )

      expect(screen.queryByText('Test Contract Listing')).not.toBeInTheDocument()
    })

    it('should render when open is true', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText('Test Contract Listing')).toBeInTheDocument()
    })

    it('should render close button', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument()
    })
  })

  describe('Tabs', () => {
    it('should render Details tab', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByRole('tab', { name: /details/i })).toBeInTheDocument()
    })

    it('should render Preview tab when contract is available', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByRole('tab', { name: /preview/i })).toBeInTheDocument()
    })

    it('should switch to Preview tab when clicked', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      const previewTab = screen.getByRole('tab', { name: /preview/i })
      fireEvent.click(previewTab)

      expect(previewTab).toHaveAttribute('aria-selected', 'true')
    })
  })

  describe('Details Tab Content', () => {
    it('should display description', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText('Long description')).toBeInTheDocument()
    })

    it('should display domain', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText('marketing')).toBeInTheDocument()
    })

    it('should display tags', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText('analytics')).toBeInTheDocument()
      expect(screen.getByText('customer')).toBeInTheDocument()
    })

    it('should display pricing model', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText('Free')).toBeInTheDocument()
    })
  })

  describe('Actions', () => {
    it('should render download button', () => {
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByRole('button', { name: /download contract/i })).toBeInTheDocument()
    })

    it('should call download mutation when download button is clicked', () => {
      const mutate = vi.fn()
      mockUseDownloadContract.mockReturnValue({
        mutate,
        isPending: false,
      })

      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      const downloadButton = screen.getByRole('button', { name: /download contract/i })
      fireEvent.click(downloadButton)

      expect(mutate).toHaveBeenCalledWith({
        listingId: 'listing-1',
        format: 'original',
      })
    })

    it('should render request access button for REQUEST_APPROVAL pricing model', () => {
      const listingWithRequest: MarketplaceListing = {
        ...mockListing,
        pricing_model: 'REQUEST_APPROVAL',
      }

      const onRequestAccess = vi.fn()
      render(
        <TestWrapper>
          <ContractDetailModal
            open={true}
            listing={listingWithRequest}
            onClose={vi.fn()}
            onRequestAccess={onRequestAccess}
          />
        </TestWrapper>
      )

      expect(screen.getByRole('button', { name: /request access/i })).toBeInTheDocument()
    })

    it('should call onRequestAccess when request access button is clicked', () => {
      const listingWithRequest: MarketplaceListing = {
        ...mockListing,
        pricing_model: 'REQUEST_APPROVAL',
      }

      const onRequestAccess = vi.fn()
      render(
        <TestWrapper>
          <ContractDetailModal
            open={true}
            listing={listingWithRequest}
            onClose={vi.fn()}
            onRequestAccess={onRequestAccess}
          />
        </TestWrapper>
      )

      const requestButton = screen.getByRole('button', { name: /request access/i })
      fireEvent.click(requestButton)

      expect(onRequestAccess).toHaveBeenCalledWith(listingWithRequest)
    })
  })

  describe('Loading States', () => {
    it('should show loading indicator when asset is loading', () => {
      mockUseAsset.mockReturnValue({
        data: undefined,
        isLoading: true,
      })

      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('should display error message when contract loading fails', () => {
      mockUseContract.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load contract'),
      })

      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText(/could not load full contract details/i)).toBeInTheDocument()
    })
  })

  describe('Close Functionality', () => {
    it('should call onClose when close button is clicked', () => {
      const onClose = vi.fn()
      render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={onClose} />
        </TestWrapper>
      )

      const closeButton = screen.getByRole('button', { name: /close/i })
      fireEvent.click(closeButton)

      expect(onClose).toHaveBeenCalled()
    })

    it('should reset to details tab when modal closes', () => {
      const onClose = vi.fn()
      const { rerender } = render(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={onClose} />
        </TestWrapper>
      )

      // Switch to preview tab
      const previewTab = screen.getByRole('tab', { name: /preview/i })
      fireEvent.click(previewTab)

      // Close modal
      const closeButton = screen.getByRole('button', { name: /close/i })
      fireEvent.click(closeButton)

      // Reopen modal
      rerender(
        <TestWrapper>
          <ContractDetailModal open={true} listing={mockListing} onClose={onClose} />
        </TestWrapper>
      )

      // Should be on details tab
      const detailsTab = screen.getByRole('tab', { name: /details/i })
      expect(detailsTab).toHaveAttribute('aria-selected', 'true')
    })
  })
})

