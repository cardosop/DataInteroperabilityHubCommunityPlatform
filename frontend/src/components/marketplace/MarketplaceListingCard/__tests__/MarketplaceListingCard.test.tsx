/**
 * MarketplaceListingCard Tests
 *
 * Comprehensive tests for the MarketplaceListingCard component covering:
 * - Card rendering with listing data
 * - Click handling
 * - Download functionality
 * - Featured state display
 * - Pricing information display
 * - Tags and domain display
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MarketplaceListingCard } from '../MarketplaceListingCard'
import type { MarketplaceListing } from '@/lib/api/marketplace'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock useDownloadContract hook
const mockMutate = vi.fn()
vi.mock('@/hooks/useMarketplace', () => ({
  useDownloadContract: vi.fn(() => ({
    mutate: mockMutate,
    isPending: false,
  })),
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
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('MarketplaceListingCard', () => {
  const mockListing: MarketplaceListing = {
    id: 'listing-1',
    tenant: 'tenant-1',
    asset: 'asset-1',
    status: 'PUBLISHED',
    pricing_model: 'FREE',
    metadata_json: {
      title: 'Test Contract',
      short_description: 'This is a test contract description',
      tags: ['analytics', 'customer'],
      domain: 'marketing',
    },
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    title: 'Test Contract',
    short_description: 'This is a test contract description',
    tags: ['analytics', 'customer'],
    domain: 'marketing',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render listing title', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByText('Test Contract')).toBeInTheDocument()
    })

    it('should render listing description', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByText(/this is a test contract description/i)).toBeInTheDocument()
    })

    it('should render domain chip', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByText('marketing')).toBeInTheDocument()
    })

    it('should render tags', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByText('analytics')).toBeInTheDocument()
      expect(screen.getByText('customer')).toBeInTheDocument()
    })

    it('should render pricing model', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByText('Free')).toBeInTheDocument()
    })

    it('should render price when available', () => {
      const listingWithPrice: MarketplaceListing = {
        ...mockListing,
        metadata_json: {
          ...mockListing.metadata_json,
          price_amount: 100,
          currency: 'USD',
        },
        price_amount: 100,
        currency: 'USD',
      }

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={listingWithPrice} />
        </TestWrapper>
      )

      expect(screen.getByText(/\$100/i)).toBeInTheDocument()
    })
  })

  describe('Featured State', () => {
    it('should display star icon when featured', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} featured />
        </TestWrapper>
      )

      // Star icon should be present (checking by aria-label or test-id if available)
      const card = screen.getByText('Test Contract').closest('.MuiCard-root')
      expect(card).toHaveStyle({ border: expect.stringContaining('2px') })
    })

    it('should not display star icon when not featured', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} featured={false} />
        </TestWrapper>
      )

      const card = screen.getByText('Test Contract').closest('.MuiCard-root')
      expect(card).not.toHaveStyle({ border: expect.stringContaining('2px') })
    })
  })

  describe('Click Handling', () => {
    it('should navigate to listing detail when card is clicked', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      const card = screen.getByText('Test Contract').closest('.MuiCard-root')
      fireEvent.click(card!)

      expect(mockNavigate).toHaveBeenCalledWith('/marketplace/listing-1')
    })

    it('should call custom onClick handler when provided', () => {
      const handleClick = vi.fn()

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} onClick={handleClick} />
        </TestWrapper>
      )

      const card = screen.getByText('Test Contract').closest('.MuiCard-root')
      fireEvent.click(card!)

      expect(handleClick).toHaveBeenCalledWith(mockListing)
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('should not navigate when clickable is false', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} clickable={false} />
        </TestWrapper>
      )

      const card = screen.getByText('Test Contract').closest('.MuiCard-root')
      fireEvent.click(card!)

      expect(mockNavigate).not.toHaveBeenCalled()
    })
  })

  describe('Actions', () => {
    it('should render view and download buttons', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByRole('button', { name: /view/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument()
    })

    it('should navigate to detail page when view is clicked', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      const viewButton = screen.getByRole('button', { name: /view/i })
      fireEvent.click(viewButton)

      expect(mockNavigate).toHaveBeenCalledWith('/marketplace/listing-1')
    })

    it('should call download mutation when download is clicked', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      const downloadButton = screen.getByRole('button', { name: /download/i })
      fireEvent.click(downloadButton)

      expect(mockMutate).toHaveBeenCalledWith({
        listingId: 'listing-1',
        format: 'original',
      })
    })

    it('should call custom onDownload handler when provided', () => {
      const handleDownload = vi.fn()

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} onDownload={handleDownload} />
        </TestWrapper>
      )

      const downloadButton = screen.getByRole('button', { name: /download/i })
      fireEvent.click(downloadButton)

      expect(handleDownload).toHaveBeenCalledWith(mockListing)
      expect(mockMutate).not.toHaveBeenCalled()
    })

    it('should disable download button when download is pending', () => {
      vi.mock('@/hooks/useMarketplace', () => ({
        useDownloadContract: vi.fn(() => ({
          mutate: mockMutate,
          isPending: true,
        })),
      }))

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      const downloadButton = screen.getByRole('button', { name: /downloading/i })
      expect(downloadButton).toBeDisabled()
    })
  })

  describe('Pricing Models', () => {
    it('should display correct text for FREE pricing model', () => {
      render(
        <TestWrapper>
          <MarketplaceListingCard listing={mockListing} />
        </TestWrapper>
      )

      expect(screen.getByText('Free')).toBeInTheDocument()
    })

    it('should display correct text for FREE_AUTO_APPROVE pricing model', () => {
      const listing: MarketplaceListing = {
        ...mockListing,
        pricing_model: 'FREE_AUTO_APPROVE',
      }

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={listing} />
        </TestWrapper>
      )

      expect(screen.getByText('Free (Auto-approve)')).toBeInTheDocument()
    })

    it('should display correct text for REQUEST_APPROVAL pricing model', () => {
      const listing: MarketplaceListing = {
        ...mockListing,
        pricing_model: 'REQUEST_APPROVAL',
      }

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={listing} />
        </TestWrapper>
      )

      expect(screen.getByText('Request Access')).toBeInTheDocument()
    })
  })

  describe('Description Truncation', () => {
    it('should truncate long descriptions by default', () => {
      const longDescription = 'a'.repeat(200)
      const listing: MarketplaceListing = {
        ...mockListing,
        short_description: longDescription,
        metadata_json: {
          ...mockListing.metadata_json,
          short_description: longDescription,
        },
      }

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={listing} />
        </TestWrapper>
      )

      const description = screen.getByText(/^a{150}\.\.\.$/i)
      expect(description).toBeInTheDocument()
    })

    it('should show full description when showFullDescription is true', () => {
      const longDescription = 'a'.repeat(200)
      const listing: MarketplaceListing = {
        ...mockListing,
        short_description: longDescription,
        metadata_json: {
          ...mockListing.metadata_json,
          short_description: longDescription,
        },
      }

      render(
        <TestWrapper>
          <MarketplaceListingCard listing={listing} showFullDescription />
        </TestWrapper>
      )

      expect(screen.getByText(longDescription)).toBeInTheDocument()
    })
  })
})

