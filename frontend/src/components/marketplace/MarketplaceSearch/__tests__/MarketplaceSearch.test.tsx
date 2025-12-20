/**
 * MarketplaceSearch Tests
 *
 * Comprehensive tests for the MarketplaceSearch component covering:
 * - Search input rendering and interaction
 * - Debounced search functionality
 * - Suggestions dropdown
 * - Recent searches dropdown
 * - Quick filters (domain, tags, pricing model)
 * - Advanced filters toggle
 * - Clear functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MarketplaceSearch } from '../MarketplaceSearch'
import type { MarketplaceSearchProps } from '../MarketplaceSearch'

// Mock debounce utility
vi.mock('@/utils/debounce', () => ({
  debounce: (fn: any) => fn, // Return function directly for testing
}))

describe('MarketplaceSearch', () => {
  const defaultProps: MarketplaceSearchProps = {
    searchQuery: '',
    onSearchChange: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render search input with placeholder', () => {
      render(<MarketplaceSearch {...defaultProps} />)

      expect(
        screen.getByPlaceholderText('Search contracts by title, description, or tags...')
      ).toBeInTheDocument()
    })

    it('should render custom placeholder', () => {
      render(<MarketplaceSearch {...defaultProps} placeholder="Custom placeholder" />)

      expect(screen.getByPlaceholderText('Custom placeholder')).toBeInTheDocument()
    })

    it('should render search icon', () => {
      render(<MarketplaceSearch {...defaultProps} />)

      expect(screen.getByLabelText(/search/i)).toBeInTheDocument()
    })

    it('should show clear button when search query has value', () => {
      render(<MarketplaceSearch {...defaultProps} searchQuery="test query" />)

      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument()
    })

    it('should not show clear button when search query is empty', () => {
      render(<MarketplaceSearch {...defaultProps} searchQuery="" />)

      expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument()
    })
  })

  describe('Search Functionality', () => {
    it('should call onSearchChange when user types', async () => {
      const onSearchChange = vi.fn()
      render(<MarketplaceSearch {...defaultProps} onSearchChange={onSearchChange} />)

      const input = screen.getByPlaceholderText(/search contracts/i)
      fireEvent.change(input, { target: { value: 'test' } })

      await waitFor(() => {
        expect(onSearchChange).toHaveBeenCalledWith('test')
      })
    })

    it('should update input value when searchQuery prop changes', () => {
      const { rerender } = render(<MarketplaceSearch {...defaultProps} searchQuery="" />)

      const input = screen.getByPlaceholderText(/search contracts/i) as HTMLInputElement
      expect(input.value).toBe('')

      rerender(<MarketplaceSearch {...defaultProps} searchQuery="new query" />)

      expect(input.value).toBe('new query')
    })

    it('should clear search when clear button is clicked', async () => {
      const onSearchChange = vi.fn()
      render(
        <MarketplaceSearch {...defaultProps} searchQuery="test" onSearchChange={onSearchChange} />
      )

      const clearButton = screen.getByRole('button', { name: /clear/i })
      fireEvent.click(clearButton)

      await waitFor(() => {
        expect(onSearchChange).toHaveBeenCalledWith('')
      })
    })
  })

  describe('Suggestions', () => {
    it('should show suggestions dropdown when input is focused and has suggestions', () => {
      const suggestions = ['suggestion 1', 'suggestion 2', 'test suggestion']
      render(<MarketplaceSearch {...defaultProps} suggestions={suggestions} />)

      const input = screen.getByPlaceholderText(/search contracts/i)
      fireEvent.change(input, { target: { value: 'test' } })
      fireEvent.focus(input)

      expect(screen.getByText('test suggestion')).toBeInTheDocument()
    })

    it('should filter suggestions based on search query', () => {
      const suggestions = ['analytics', 'customer data', 'sales data']
      render(<MarketplaceSearch {...defaultProps} suggestions={suggestions} />)

      const input = screen.getByPlaceholderText(/search contracts/i)
      fireEvent.change(input, { target: { value: 'analytics' } })
      fireEvent.focus(input)

      expect(screen.getByText('analytics')).toBeInTheDocument()
      expect(screen.queryByText('customer data')).not.toBeInTheDocument()
    })

    it('should call onSearchChange when suggestion is clicked', async () => {
      const onSearchChange = vi.fn()
      const suggestions = ['test suggestion']
      render(
        <MarketplaceSearch
          {...defaultProps}
          suggestions={suggestions}
          onSearchChange={onSearchChange}
        />
      )

      const input = screen.getByPlaceholderText(/search contracts/i)
      fireEvent.change(input, { target: { value: 'test' } })
      fireEvent.focus(input)

      const suggestion = screen.getByText('test suggestion')
      fireEvent.click(suggestion)

      await waitFor(() => {
        expect(onSearchChange).toHaveBeenCalledWith('test suggestion')
      })
    })
  })

  describe('Recent Searches', () => {
    it('should show recent searches dropdown when input is focused and empty', () => {
      const recentSearches = ['recent 1', 'recent 2']
      render(<MarketplaceSearch {...defaultProps} recentSearches={recentSearches} />)

      const input = screen.getByPlaceholderText(/search contracts/i)
      fireEvent.focus(input)

      expect(screen.getByText('Recent Searches')).toBeInTheDocument()
      expect(screen.getByText('recent 1')).toBeInTheDocument()
      expect(screen.getByText('recent 2')).toBeInTheDocument()
    })

    it('should call onRecentSearchClick when recent search is clicked', async () => {
      const onRecentSearchClick = vi.fn()
      const onSearchChange = vi.fn()
      const recentSearches = ['recent search']
      render(
        <MarketplaceSearch
          {...defaultProps}
          recentSearches={recentSearches}
          onRecentSearchClick={onRecentSearchClick}
          onSearchChange={onSearchChange}
        />
      )

      const input = screen.getByPlaceholderText(/search contracts/i)
      fireEvent.focus(input)

      const recentSearch = screen.getByText('recent search')
      fireEvent.click(recentSearch)

      await waitFor(() => {
        expect(onRecentSearchClick).toHaveBeenCalledWith('recent search')
        expect(onSearchChange).toHaveBeenCalledWith('recent search')
      })
    })
  })

  describe('Quick Filters', () => {
    it('should show domain filter when availableDomains provided', () => {
      const availableDomains = ['marketing', 'sales']
      const onDomainChange = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          availableDomains={availableDomains}
          onDomainChange={onDomainChange}
          showAdvancedFilters={true}
        />
      )

      expect(screen.getByLabelText(/domain/i)).toBeInTheDocument()
    })

    it('should show tags filter when availableTags provided', () => {
      const availableTags = ['analytics', 'customer']
      const onTagsChange = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          availableTags={availableTags}
          onTagsChange={onTagsChange}
          showAdvancedFilters={true}
        />
      )

      expect(screen.getByLabelText(/tags/i)).toBeInTheDocument()
    })

    it('should show pricing model filter when onPricingModelChange provided', () => {
      const onPricingModelChange = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          onPricingModelChange={onPricingModelChange}
          showAdvancedFilters={true}
        />
      )

      expect(screen.getByLabelText(/access mode/i)).toBeInTheDocument()
    })

    it('should call onDomainChange when domain filter changes', () => {
      const onDomainChange = vi.fn()
      const availableDomains = ['marketing', 'sales']
      render(
        <MarketplaceSearch
          {...defaultProps}
          availableDomains={availableDomains}
          onDomainChange={onDomainChange}
          showAdvancedFilters={true}
        />
      )

      const domainInput = screen.getByLabelText(/domain/i)
      fireEvent.mousedown(domainInput)
      const option = screen.getByText('marketing')
      fireEvent.click(option)

      expect(onDomainChange).toHaveBeenCalledWith('marketing')
    })

    it('should show clear filters button when filters are active', () => {
      const onDomainChange = vi.fn()
      const onTagsChange = vi.fn()
      const onPricingModelChange = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          domain="marketing"
          selectedTags={['analytics']}
          pricingModel="FREE"
          availableDomains={['marketing']}
          onDomainChange={onDomainChange}
          onTagsChange={onTagsChange}
          onPricingModelChange={onPricingModelChange}
          showAdvancedFilters={true}
        />
      )

      expect(screen.getByRole('button', { name: /clear filters/i })).toBeInTheDocument()
    })

    it('should clear all filters when clear button is clicked', () => {
      const onDomainChange = vi.fn()
      const onTagsChange = vi.fn()
      const onPricingModelChange = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          domain="marketing"
          selectedTags={['analytics']}
          pricingModel="FREE"
          availableDomains={['marketing']}
          onDomainChange={onDomainChange}
          onTagsChange={onTagsChange}
          onPricingModelChange={onPricingModelChange}
          showAdvancedFilters={true}
        />
      )

      const clearButton = screen.getByRole('button', { name: /clear filters/i })
      fireEvent.click(clearButton)

      expect(onDomainChange).toHaveBeenCalledWith(null)
      expect(onTagsChange).toHaveBeenCalledWith([])
      expect(onPricingModelChange).toHaveBeenCalledWith('')
    })
  })

  describe('Advanced Filters Toggle', () => {
    it('should show advanced filters toggle when onAdvancedFiltersToggle provided', () => {
      const onAdvancedFiltersToggle = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          onAdvancedFiltersToggle={onAdvancedFiltersToggle}
        />
      )

      expect(screen.getByRole('button', { name: /filter/i })).toBeInTheDocument()
    })

    it('should call onAdvancedFiltersToggle when toggle button is clicked', () => {
      const onAdvancedFiltersToggle = vi.fn()
      render(
        <MarketplaceSearch
          {...defaultProps}
          onAdvancedFiltersToggle={onAdvancedFiltersToggle}
        />
      )

      const toggleButton = screen.getByRole('button', { name: /filter/i })
      fireEvent.click(toggleButton)

      expect(onAdvancedFiltersToggle).toHaveBeenCalledWith(true)
    })
  })
})

