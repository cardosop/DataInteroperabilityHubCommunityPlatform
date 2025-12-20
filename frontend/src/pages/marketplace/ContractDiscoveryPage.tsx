/**
 * Contract Discovery Page
 *
 * Dedicated page for discovering and accessing contracts from the marketplace.
 * Features:
 * - Contract cards with preview
 * - Contract detail modal
 * - Contract download
 * - Contract request access
 */

import React, { useState, useMemo, useCallback } from 'react'
import {
  Container,
  Box,
  Typography,
  Grid,
  IconButton,
  Tooltip,
  Snackbar,
  Alert,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
} from '@mui/icons-material'
import { useMarketplaceContracts } from '@/hooks/useMarketplace'
import type {
  MarketplaceListing,
  SearchMarketplaceContractsParams,
} from '@/lib/api/marketplace'
import { MarketplaceListingCard } from '@/components/marketplace/MarketplaceListingCard/MarketplaceListingCard'
import { ContractDetailModal } from '@/components/marketplace/ContractDetailModal'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { SearchBar } from '@/components/forms/SearchBar'
import { useDownloadContract } from '@/hooks/useMarketplace'

/**
 * ContractDiscoveryPage Component
 */
export const ContractDiscoveryPage: React.FC = () => {
  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Search state
  const [searchQuery, setSearchQuery] = useState<string>('')

  // Filter state
  const [domainFilter, setDomainFilter] = useState<string>('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])

  // Modal state
  const [selectedListing, setSelectedListing] = useState<MarketplaceListing | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  // Notification state
  const [notification, setNotification] = useState<{
    open: boolean
    message: string
    severity: 'success' | 'error' | 'info' | 'warning'
  }>({
    open: false,
    message: '',
    severity: 'info',
  })

  // Download hook
  const downloadContract = useDownloadContract({
    onSuccess: (data) => {
      // Create blob and download
      const blob = new Blob([data.contract_content], {
        type: data.format === 'JSON' ? 'application/json' : 'text/plain',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = data.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      setNotification({
        open: true,
        message: 'Contract downloaded successfully',
        severity: 'success',
      })
    },
    onError: (error) => {
      setNotification({
        open: true,
        message: `Failed to download contract: ${error.message}`,
        severity: 'error',
      })
    },
  })

  // Build query parameters
  const queryParams = useMemo<SearchMarketplaceContractsParams>(() => {
    const params: SearchMarketplaceContractsParams = {
      page,
      page_size: pageSize,
    }

    if (searchQuery.trim()) {
      params.search = searchQuery.trim()
    }
    if (domainFilter.trim()) {
      params.domain = domainFilter.trim()
    }
    if (selectedTags.length > 0) {
      params.tags = selectedTags
    }

    return params
  }, [page, pageSize, searchQuery, domainFilter, selectedTags])

  // Fetch marketplace contracts
  const { data, isLoading, error, refetch, isFetching } = useMarketplaceContracts(queryParams)

  // Handle card click - open detail modal
  const handleCardClick = useCallback((listing: MarketplaceListing) => {
    setSelectedListing(listing)
    setIsModalOpen(true)
  }, [])

  // Handle view click - open detail modal
  const handleViewClick = useCallback((listing: MarketplaceListing) => {
    setSelectedListing(listing)
    setIsModalOpen(true)
  }, [])

  // Handle download click
  const handleDownloadClick = useCallback((listing: MarketplaceListing) => {
    downloadContract.mutate({
      listingId: listing.id,
      format: 'original',
    })
  }, [downloadContract])

  // Handle request access
  const handleRequestAccess = useCallback((listing: MarketplaceListing) => {
    // TODO: Implement actual API call for access request
    // For now, show a notification
    setNotification({
      open: true,
      message: `Access request submitted for "${listing.title || listing.metadata_json?.title || 'contract'}"`,
      severity: 'info',
    })
    setIsModalOpen(false)
  }, [])

  // Handle modal close
  const handleModalClose = useCallback(() => {
    setIsModalOpen(false)
    setSelectedListing(null)
  }, [])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(searchQuery.trim() || domainFilter.trim() || selectedTags.length > 0)
  }, [searchQuery, domainFilter, selectedTags])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading contracts..." />
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
            title="Failed to load contracts"
            message={error.message || 'An error occurred while loading contracts.'}
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
                Contract Discovery
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Discover and access data contracts from the marketplace
              </Typography>
            </Box>

            <NoResultsEmptyState
              title="No contracts found"
              description="Try adjusting your search or filters to find what you're looking for."
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
              Contract Discovery
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Discover and access data contracts from the marketplace
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

  // Main content
  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Contract Discovery
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Discover and access data contracts from the marketplace ({data.count} total)
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

        {/* Search */}
        <Box sx={{ mb: 3 }}>
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search contracts by title, description, or tags..."
            showClear
          />
        </Box>

        {/* Results count */}
        {hasActiveFilters && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {data.count} contract{data.count !== 1 ? 's' : ''} found
            </Typography>
          </Box>
        )}

        {/* Contract Cards Grid */}
        <Grid container spacing={3}>
          {data.results.map((listing) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={listing.id}>
              <MarketplaceListingCard
                listing={listing}
                onClick={handleCardClick}
                onView={handleViewClick}
                onDownload={handleDownloadClick}
                showActions
              />
            </Grid>
          ))}
        </Grid>

        {/* Pagination */}
        {data.count > pageSize && (
          <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
            <EnhancedPagination
              page={page}
              totalPages={Math.ceil(data.count / pageSize)}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize)
                setPage(1)
              }}
              totalItems={data.count}
              pageSizeOptions={[12, 24, 48, 96]}
            />
          </Box>
        )}

        {/* Contract Detail Modal */}
        <ContractDetailModal
          open={isModalOpen}
          listing={selectedListing}
          onClose={handleModalClose}
          onRequestAccess={handleRequestAccess}
        />

        {/* Notification Snackbar */}
        <Snackbar
          open={notification.open}
          autoHideDuration={6000}
          onClose={() => setNotification({ ...notification, open: false })}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        >
          <Alert
            onClose={() => setNotification({ ...notification, open: false })}
            severity={notification.severity}
            sx={{ width: '100%' }}
          >
            {notification.message}
          </Alert>
        </Snackbar>
      </Box>
    </Container>
  )
}

ContractDiscoveryPage.displayName = 'ContractDiscoveryPage'

