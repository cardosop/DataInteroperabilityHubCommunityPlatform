/**
 * Marketplace Page
 *
 * Comprehensive marketplace page with:
 * - Contract discovery interface
 * - Search functionality with debouncing
 * - Filtering (domain, category/tags, pricing model)
 * - Sorting
 * - Featured contracts section
 * - Empty state
 * - Loading state
 * - Error state
 */

import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Button,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  Autocomplete,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  FilterList as FilterListIcon,
  Star as StarIcon,
  Clear as ClearIcon,
} from '@mui/icons-material'
import { useMarketplaceContracts } from '@/hooks/useMarketplace'
import type {
  MarketplaceListing,
  PricingModel,
  SearchMarketplaceContractsParams,
} from '@/lib/api/marketplace'
import { MarketplaceListingCard } from '@/components/marketplace'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { SearchBar } from '@/components/forms/SearchBar'
import { debounce } from '@/utils/debounce'

/**
 * Sort options for marketplace listings
 */
type SortOption = 'relevance' | 'newest' | 'oldest' | 'title_asc' | 'title_desc' | 'price_asc' | 'price_desc'

/**
 * Get sort option display text
 */
const getSortOptionText = (option: SortOption): string => {
  switch (option) {
    case 'relevance':
      return 'Relevance'
    case 'newest':
      return 'Newest First'
    case 'oldest':
      return 'Oldest First'
    case 'title_asc':
      return 'Title (A-Z)'
    case 'title_desc':
      return 'Title (Z-A)'
    case 'price_asc':
      return 'Price (Low to High)'
    case 'price_desc':
      return 'Price (High to Low)'
    default:
      return option
  }
}

/**
 * Marketplace Page Component
 */
export const MarketplacePage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Search state
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [debouncedSearch, setDebouncedSearch] = useState<string>('')

  // Filter state
  const [domainFilter, setDomainFilter] = useState<string>('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [pricingModelFilter, setPricingModelFilter] = useState<PricingModel | ''>('')
  const [priceMin, setPriceMin] = useState<number | ''>('')
  const [priceMax, setPriceMax] = useState<number | ''>('')

  // Sort state
  const [sortOption, setSortOption] = useState<SortOption>('relevance')

  // Debounce search query
  const debouncedSearchRef = useRef(
    debounce((value: string) => {
      setDebouncedSearch(value)
      setPage(1) // Reset to first page on search
    }, 500)
  )

  useEffect(() => {
    debouncedSearchRef.current(searchQuery)
  }, [searchQuery])

  // Build query parameters
  const queryParams = useMemo<SearchMarketplaceContractsParams>(() => {
    const params: SearchMarketplaceContractsParams = {
      page,
      page_size: pageSize,
    }

    if (debouncedSearch.trim()) {
      params.search = debouncedSearch.trim()
    }
    if (domainFilter.trim()) {
      params.domain = domainFilter.trim()
    }
    if (selectedTags.length > 0) {
      params.tags = selectedTags
    }
    if (pricingModelFilter) {
      params.access_mode = pricingModelFilter
    }
    if (priceMin !== '') {
      params.price_min = Number(priceMin)
    }
    if (priceMax !== '') {
      params.price_max = Number(priceMax)
    }

    // Handle sorting
    // Note: Backend may not support all sort options, so we'll handle some client-side
    // For now, we'll use backend sorting where possible
    switch (sortOption) {
      case 'newest':
        // Backend should sort by published_at desc
        break
      case 'oldest':
        // Backend should sort by published_at asc
        break
      default:
        break
    }

    return params
  }, [
    page,
    pageSize,
    debouncedSearch,
    domainFilter,
    selectedTags,
    pricingModelFilter,
    priceMin,
    priceMax,
    sortOption,
  ])

  // Fetch marketplace contracts
  const { data, isLoading, error, refetch, isFetching } = useMarketplaceContracts(queryParams)

  // Extract unique domains and tags from all listings for filter options
  const { domains, tags: allTags } = useMemo(() => {
    if (!data?.results) {
      return { domains: [], tags: [] }
    }

    const domainSet = new Set<string>()
    const tagSet = new Set<string>()

    data.results.forEach((listing) => {
      const domain = listing.domain || listing.metadata_json?.domain
      if (domain) {
        domainSet.add(domain)
      }

      const listingTags = listing.tags || listing.metadata_json?.tags || []
      listingTags.forEach((tag) => tagSet.add(tag))
    })

    return {
      domains: Array.from(domainSet).sort(),
      tags: Array.from(tagSet).sort(),
    }
  }, [data?.results])

  // Get featured contracts (recently published, within last 30 days)
  const featuredContracts = useMemo(() => {
    if (!data?.results) return []

    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

    return data.results
      .filter((listing) => {
        if (!listing.published_at) return false
        const publishedDate = new Date(listing.published_at)
        return publishedDate >= thirtyDaysAgo && listing.status === 'PUBLISHED'
      })
      .slice(0, 6) // Show up to 6 featured contracts
  }, [data?.results])

  // Client-side sorting for listings (when backend doesn't support the sort option)
  const sortedListings = useMemo(() => {
    if (!data?.results) return []

    let sorted = [...data.results]

    switch (sortOption) {
      case 'title_asc':
        sorted.sort((a, b) => {
          const titleA = (a.title || a.metadata_json?.title || '').toLowerCase()
          const titleB = (b.title || b.metadata_json?.title || '').toLowerCase()
          return titleA.localeCompare(titleB)
        })
        break
      case 'title_desc':
        sorted.sort((a, b) => {
          const titleA = (a.title || a.metadata_json?.title || '').toLowerCase()
          const titleB = (b.title || b.metadata_json?.title || '').toLowerCase()
          return titleB.localeCompare(titleA)
        })
        break
      case 'price_asc':
        sorted.sort((a, b) => {
          const priceA = a.price_amount || a.metadata_json?.price_amount || 0
          const priceB = b.price_amount || b.metadata_json?.price_amount || 0
          return priceA - priceB
        })
        break
      case 'price_desc':
        sorted.sort((a, b) => {
          const priceA = a.price_amount || a.metadata_json?.price_amount || 0
          const priceB = b.price_amount || b.metadata_json?.price_amount || 0
          return priceB - priceA
        })
        break
      default:
        // Keep original order for relevance, newest, oldest (handled by backend)
        break
    }

    return sorted
  }, [data?.results, sortOption])

  // Handle filter clear
  const handleClearFilters = useCallback(() => {
    setSearchQuery('')
    setDebouncedSearch('')
    setDomainFilter('')
    setSelectedTags([])
    setPricingModelFilter('')
    setPriceMin('')
    setPriceMax('')
    setPage(1)
  }, [])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(
      debouncedSearch.trim() ||
      domainFilter.trim() ||
      selectedTags.length > 0 ||
      pricingModelFilter ||
      priceMin !== '' ||
      priceMax !== ''
    )
  }, [debouncedSearch, domainFilter, selectedTags, pricingModelFilter, priceMin, priceMax])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading marketplace contracts..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (error) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load marketplace"
            message={error.message || 'An error occurred while loading marketplace contracts.'}
            onRetry={() => refetch()}
          />
        </Box>
      </Container>
    )
  }

  // Empty state - no data at all
  if (!data || data.count === 0) {
    if (hasActiveFilters) {
      // No results from search/filter
      return (
        <Container maxWidth="xl">
          <Box sx={{ py: 4 }}>
            <Box sx={{ mb: 4 }}>
              <Typography variant="h4" gutterBottom>
                Marketplace
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Discover and access data contracts
              </Typography>
            </Box>

            <NoResultsEmptyState
              title="No contracts found"
              description="Try adjusting your search or filters to find what you're looking for."
              primaryAction={{
                label: 'Clear Filters',
                onClick: handleClearFilters,
                primary: true,
              }}
            />
          </Box>
        </Container>
      )
    }

    // No data at all
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <Box sx={{ mb: 4 }}>
            <Typography variant="h4" gutterBottom>
              Marketplace
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Discover and access data contracts
            </Typography>
          </Box>

          <NoDataEmptyState
            title="No contracts available"
            description="There are no published contracts in the marketplace yet."
          />
        </Box>
      </Container>
    )
  }

  // Main content - marketplace listings
  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Marketplace
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Discover and access data contracts ({data.count} total)
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetch()} disabled={isFetching}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Featured Contracts Section */}
        {featuredContracts.length > 0 && (
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <StarIcon sx={{ color: 'primary.main' }} />
              <Typography variant="h5" component="h2">
                Featured Contracts
              </Typography>
            </Box>
            <Grid container spacing={3}>
              {featuredContracts.map((listing) => (
                <Grid item xs={12} sm={6} md={4} key={listing.id}>
                  <MarketplaceListingCard listing={listing} featured />
                </Grid>
              ))}
            </Grid>
          </Box>
        )}

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Search */}
            <Box>
              <SearchBar
                value={searchQuery}
                onChange={setSearchQuery}
                placeholder="Search contracts by title, description, or tags..."
                showClear
              />
            </Box>

            {/* Filter controls */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
              <FilterListIcon sx={{ color: 'text.secondary' }} />
              <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
                Filters:
              </Typography>

              {/* Domain filter */}
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel>Domain</InputLabel>
                <Select
                  value={domainFilter}
                  label="Domain"
                  onChange={(e) => {
                    setDomainFilter(e.target.value)
                    setPage(1)
                  }}
                >
                  <MenuItem value="">
                    <em>All Domains</em>
                  </MenuItem>
                  {domains.map((domain) => (
                    <MenuItem key={domain} value={domain}>
                      {domain}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Tags filter */}
              <Autocomplete
                multiple
                size="small"
                options={allTags}
                value={selectedTags}
                onChange={(_, newValue) => {
                  setSelectedTags(newValue)
                  setPage(1)
                }}
                renderInput={(params) => (
                  <TextField {...params} label="Tags" placeholder="Select tags" />
                )}
                sx={{ minWidth: 200 }}
              />

              {/* Pricing model filter */}
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>Access Mode</InputLabel>
                <Select
                  value={pricingModelFilter}
                  label="Access Mode"
                  onChange={(e) => {
                    setPricingModelFilter(e.target.value as PricingModel | '')
                    setPage(1)
                  }}
                >
                  <MenuItem value="">
                    <em>All Access Modes</em>
                  </MenuItem>
                  <MenuItem value="FREE">Free</MenuItem>
                  <MenuItem value="FREE_AUTO_APPROVE">Free (Auto-approve)</MenuItem>
                  <MenuItem value="REQUEST_APPROVAL">Request Access</MenuItem>
                </Select>
              </FormControl>

              {/* Price range */}
              <TextField
                size="small"
                label="Min Price"
                type="number"
                value={priceMin}
                onChange={(e) => {
                  const value = e.target.value === '' ? '' : Number(e.target.value)
                  setPriceMin(value)
                  setPage(1)
                }}
                sx={{ width: 120 }}
                InputProps={{
                  inputProps: { min: 0 },
                }}
              />
              <TextField
                size="small"
                label="Max Price"
                type="number"
                value={priceMax}
                onChange={(e) => {
                  const value = e.target.value === '' ? '' : Number(e.target.value)
                  setPriceMax(value)
                  setPage(1)
                }}
                sx={{ width: 120 }}
                InputProps={{
                  inputProps: { min: 0 },
                }}
              />

              {/* Sort */}
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>Sort By</InputLabel>
                <Select
                  value={sortOption}
                  label="Sort By"
                  onChange={(e) => {
                    setSortOption(e.target.value as SortOption)
                  }}
                >
                  <MenuItem value="relevance">Relevance</MenuItem>
                  <MenuItem value="newest">Newest First</MenuItem>
                  <MenuItem value="oldest">Oldest First</MenuItem>
                  <MenuItem value="title_asc">Title (A-Z)</MenuItem>
                  <MenuItem value="title_desc">Title (Z-A)</MenuItem>
                  <MenuItem value="price_asc">Price (Low to High)</MenuItem>
                  <MenuItem value="price_desc">Price (High to Low)</MenuItem>
                </Select>
              </FormControl>

              {/* Clear filters */}
              {hasActiveFilters && (
                <Button
                  size="small"
                  startIcon={<ClearIcon />}
                  onClick={handleClearFilters}
                  variant="outlined"
                >
                  Clear Filters
                </Button>
              )}
            </Box>
          </Box>
        </Paper>

        {/* Results count */}
        {hasActiveFilters && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {data.count} contract{data.count !== 1 ? 's' : ''} found
            </Typography>
          </Box>
        )}

        {/* Listings Grid */}
        <Grid container spacing={3}>
          {sortedListings.map((listing) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={listing.id}>
              <MarketplaceListingCard listing={listing} />
            </Grid>
          ))}
        </Grid>

        {/* Pagination */}
        {data.count > pageSize && (
          <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
            <EnhancedPagination
              count={Math.ceil(data.count / pageSize)}
              page={page}
              onChange={(_, newPage) => setPage(newPage)}
              pageSize={pageSize}
              onPageSizeChange={setPageSize}
              showPageSizeSelector
            />
          </Box>
        )}
      </Box>
    </Container>
  )
}

MarketplacePage.displayName = 'MarketplacePage'

