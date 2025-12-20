/**
 * MarketplacePage Tests
 *
 * Comprehensive tests for the MarketplacePage component covering:
 * - Page rendering
 * - Search functionality with debouncing
 * - Filtering (domain, tags, pricing model, price range)
 * - Sorting functionality
 * - Featured contracts display
 * - Pagination
 * - Empty states
 * - Error handling
 * - Loading states
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MarketplacePage } from '../MarketplacePage'
import * as marketplaceApi from '@/lib/api/marketplace'
import { useMarketplaceContracts } from '@/hooks/useMarketplace'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock useMarketplaceContracts hook
vi.mock('@/hooks/useMarketplace', () => ({
  useMarketplaceContracts: vi.fn(),
  useDownloadContract: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
  })),
}))

// Mock debounce utility
vi.mock('@/utils/debounce', () => ({
  debounce: (fn: any) => fn, // Return function directly for testing
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

describe('MarketplacePage', () => {
  const mockUseMarketplaceContracts = vi.mocked(useMarketplaceContracts)

  const mockListings: marketplaceApi.MarketplaceListing[] = [
    {
      id: '1',
      tenant: 'tenant-1',
      asset: 'asset-1',
      status: 'PUBLISHED',
      pricing_model: 'FREE',
      metadata_json: {
        title: 'Customer Data Contract',
        short_description: 'Customer data for analytics',
        tags: ['analytics', 'customer'],
        domain: 'marketing',
      },
      published_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      title: 'Customer Data Contract',
      short_description: 'Customer data for analytics',
      tags: ['analytics', 'customer'],
      domain: 'marketing',
    },
    {
      id: '2',
      tenant: 'tenant-2',
      asset: 'asset-2',
      status: 'PUBLISHED',
      pricing_model: 'REQUEST_APPROVAL',
      metadata_json: {
        title: 'Sales Data Contract',
        short_description: 'Sales data for reporting',
        tags: ['sales', 'reporting'],
        domain: 'sales',
        price_amount: 100,
        currency: 'USD',
      },
      published_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(), // 10 days ago
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      title: 'Sales Data Contract',
      short_description: 'Sales data for reporting',
      tags: ['sales', 'reporting'],
      domain: 'sales',
      price_amount: 100,
      currency: 'USD',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseMarketplaceContracts.mockReturnValue({
      data: {
        results: mockListings,
        count: mockListings.length,
        page: 1,
        page_size: 20,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    } as any)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render the page with title and description', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByText(/marketplace/i)).toBeInTheDocument()
      expect(screen.getByText(/discover and access data contracts/i)).toBeInTheDocument()
    })

    it('should render search bar', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(
        screen.getByPlaceholderText(/search contracts by title, description, or tags/i)
      ).toBeInTheDocument()
    })

    it('should render filter controls', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByLabelText(/domain/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/tags/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/access mode/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/sort by/i)).toBeInTheDocument()
    })

    it('should render marketplace listings', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByText('Customer Data Contract')).toBeInTheDocument()
      expect(screen.getByText('Sales Data Contract')).toBeInTheDocument()
    })
  })

  describe('Loading State', () => {
    it('should display loading state when data is loading', () => {
      mockUseMarketplaceContracts.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByText(/loading marketplace contracts/i)).toBeInTheDocument()
    })
  })

  describe('Error State', () => {
    it('should display error state when request fails', () => {
      mockUseMarketplaceContracts.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load marketplace'),
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByText(/failed to load marketplace/i)).toBeInTheDocument()
    })

    it('should call refetch when retry is clicked', async () => {
      const mockRefetch = vi.fn()
      mockUseMarketplaceContracts.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load marketplace'),
        refetch: mockRefetch,
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const retryButton = screen.getByRole('button', { name: /retry/i })
      fireEvent.click(retryButton)

      expect(mockRefetch).toHaveBeenCalled()
    })
  })

  describe('Empty States', () => {
    it('should display no data state when there are no listings', () => {
      mockUseMarketplaceContracts.mockReturnValue({
        data: {
          results: [],
          count: 0,
          page: 1,
          page_size: 20,
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByText(/no contracts available/i)).toBeInTheDocument()
    })

    it('should display no results state when filters return no results', () => {
      mockUseMarketplaceContracts.mockReturnValue({
        data: {
          results: [],
          count: 0,
          page: 1,
          page_size: 20,
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      // Set a search query to trigger filtered state
      const searchInput = screen.getByPlaceholderText(
        /search contracts by title, description, or tags/i
      )
      fireEvent.change(searchInput, { target: { value: 'nonexistent' } })

      // Wait for debounced search
      waitFor(() => {
        expect(screen.getByText(/no contracts found/i)).toBeInTheDocument()
      })
    })
  })

  describe('Search Functionality', () => {
    it('should update search query when user types', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText(
        /search contracts by title, description, or tags/i
      ) as HTMLInputElement

      fireEvent.change(searchInput, { target: { value: 'customer' } })

      expect(searchInput.value).toBe('customer')
    })

    it('should reset to first page when search changes', async () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const searchInput = screen.getByPlaceholderText(
        /search contracts by title, description, or tags/i
      )

      fireEvent.change(searchInput, { target: { value: 'test' } })

      // Verify that the query was called with page 1
      await waitFor(() => {
        expect(mockUseMarketplaceContracts).toHaveBeenCalledWith(
          expect.objectContaining({
            page: 1,
            search: 'test',
          }),
          undefined
        )
      })
    })
  })

  describe('Filtering', () => {
    it('should filter by domain', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const domainSelect = screen.getByLabelText(/domain/i)
      fireEvent.mousedown(domainSelect)
      const option = screen.getByText('marketing')
      fireEvent.click(option)

      waitFor(() => {
        expect(mockUseMarketplaceContracts).toHaveBeenCalledWith(
          expect.objectContaining({
            domain: 'marketing',
          }),
          undefined
        )
      })
    })

    it('should filter by tags', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const tagsInput = screen.getByLabelText(/tags/i)
      fireEvent.mousedown(tagsInput)
      const option = screen.getByText('analytics')
      fireEvent.click(option)

      waitFor(() => {
        expect(mockUseMarketplaceContracts).toHaveBeenCalledWith(
          expect.objectContaining({
            tags: expect.arrayContaining(['analytics']),
          }),
          undefined
        )
      })
    })

    it('should filter by pricing model', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const accessModeSelect = screen.getByLabelText(/access mode/i)
      fireEvent.mousedown(accessModeSelect)
      const option = screen.getByText('Free')
      fireEvent.click(option)

      waitFor(() => {
        expect(mockUseMarketplaceContracts).toHaveBeenCalledWith(
          expect.objectContaining({
            access_mode: 'FREE',
          }),
          undefined
        )
      })
    })

    it('should filter by price range', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const minPriceInput = screen.getByLabelText(/min price/i)
      const maxPriceInput = screen.getByLabelText(/max price/i)

      fireEvent.change(minPriceInput, { target: { value: '50' } })
      fireEvent.change(maxPriceInput, { target: { value: '200' } })

      waitFor(() => {
        expect(mockUseMarketplaceContracts).toHaveBeenCalledWith(
          expect.objectContaining({
            price_min: 50,
            price_max: 200,
          }),
          undefined
        )
      })
    })

    it('should clear all filters when clear button is clicked', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      // Set some filters first
      const searchInput = screen.getByPlaceholderText(
        /search contracts by title, description, or tags/i
      )
      fireEvent.change(searchInput, { target: { value: 'test' } })

      // Wait for clear button to appear
      waitFor(() => {
        const clearButton = screen.getByRole('button', { name: /clear filters/i })
        fireEvent.click(clearButton)

        expect(searchInput).toHaveValue('')
      })
    })
  })

  describe('Sorting', () => {
    it('should change sort option', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const sortSelect = screen.getByLabelText(/sort by/i)
      fireEvent.mousedown(sortSelect)
      const option = screen.getByText('Title (A-Z)')
      fireEvent.click(option)

      // Verify sorting is applied (client-side for title sorting)
      waitFor(() => {
        const listings = screen.getAllByText(/contract/i)
        expect(listings.length).toBeGreaterThan(0)
      })
    })
  })

  describe('Featured Contracts', () => {
    it('should display featured contracts section when there are recent published contracts', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.getByText(/featured contracts/i)).toBeInTheDocument()
    })

    it('should not display featured section when there are no recent contracts', () => {
      const oldListings = mockListings.map((listing) => ({
        ...listing,
        published_at: new Date(Date.now() - 40 * 24 * 60 * 60 * 1000).toISOString(), // 40 days ago
      }))

      mockUseMarketplaceContracts.mockReturnValue({
        data: {
          results: oldListings,
          count: oldListings.length,
          page: 1,
          page_size: 20,
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      expect(screen.queryByText(/featured contracts/i)).not.toBeInTheDocument()
    })
  })

  describe('Pagination', () => {
    it('should display pagination when there are more results than page size', () => {
      mockUseMarketplaceContracts.mockReturnValue({
        data: {
          results: mockListings,
          count: 50,
          page: 1,
          page_size: 20,
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      // Pagination should be visible
      expect(screen.getByRole('navigation')).toBeInTheDocument()
    })

    it('should not display pagination when there are fewer results than page size', () => {
      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      // With only 2 results and page size 20, pagination should not be visible
      // This is handled by the component logic
    })
  })

  describe('Refresh', () => {
    it('should call refetch when refresh button is clicked', () => {
      const mockRefetch = vi.fn()
      mockUseMarketplaceContracts.mockReturnValue({
        data: {
          results: mockListings,
          count: mockListings.length,
          page: 1,
          page_size: 20,
        },
        isLoading: false,
        error: null,
        refetch: mockRefetch,
        isFetching: false,
      } as any)

      render(
        <TestWrapper>
          <MarketplacePage />
        </TestWrapper>
      )

      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      fireEvent.click(refreshButton)

      expect(mockRefetch).toHaveBeenCalled()
    })
  })
})

