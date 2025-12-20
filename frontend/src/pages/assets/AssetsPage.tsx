/**
 * Assets Page
 *
 * Comprehensive asset list page with:
 * - Asset list with server-side pagination
 * - Search and filtering
 * - Sorting
 * - Empty state
 * - Loading state
 * - Error state
 */

import React, { useState, useMemo, useCallback } from 'react'
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
} from '@mui/material'
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material'
import { useAssets, type Asset } from '@/hooks/useAssets'
import { useRealtimeAssets } from '@/hooks/useRealtimeAssets'
import { EnhancedTable, type TableColumn } from '@/components/data-display/Table'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { SearchBar } from '@/components/forms/SearchBar'
import { TableSortIcon } from '@/components/data-display/Table/TableSortIcon'
import { AssetStatus, AssetVisibility } from '@/lib/api/assets'
// Date formatting utility
const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
  return date.toLocaleDateString()
}

/**
 * Assets Page Component
 */
export const AssetsPage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Search and filter state
  const [search, setSearch] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<AssetStatus | ''>('')
  const [visibilityFilter, setVisibilityFilter] = useState<AssetVisibility | ''>('')
  const [domainFilter, setDomainFilter] = useState<string>('')

  // Sorting state
  const [ordering, setOrdering] = useState<string>('-created_at')

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: Record<string, any> = {
      page,
      page_size: pageSize,
      ordering,
    }

    if (search.trim()) {
      params.search = search.trim()
    }
    if (statusFilter) {
      params.status = statusFilter
    }
    if (visibilityFilter) {
      params.visibility = visibilityFilter
    }
    if (domainFilter.trim()) {
      params.domain = domainFilter.trim()
    }

    return params
  }, [page, pageSize, ordering, search, statusFilter, visibilityFilter, domainFilter])

  // Fetch assets
  const { data, isLoading, error, refetch, isFetching } = useAssets(queryParams)

  // Subscribe to real-time asset updates
  useRealtimeAssets({
    showNotifications: true,
    enabled: true,
  })

  // Handle sorting - server-side
  const handleSort = useCallback((columnId: string) => {
    // Parse current ordering
    const currentColumn = ordering.startsWith('-') ? ordering.slice(1) : ordering
    const currentDirection = ordering.startsWith('-') ? 'desc' : 'asc'

    if (currentColumn === columnId) {
      // Cycle: asc -> desc -> default
      if (currentDirection === 'asc') {
        setOrdering(`-${columnId}`)
      } else {
        setOrdering('-created_at') // Default
      }
    } else {
      // New column, start with asc
      setOrdering(columnId)
    }
  }, [ordering])

  // Get current sort state for a column
  const getSortState = useCallback((columnId: string): 'asc' | 'desc' | null => {
    const currentColumn = ordering.startsWith('-') ? ordering.slice(1) : ordering
    if (currentColumn !== columnId) return null
    return ordering.startsWith('-') ? 'desc' : 'asc'
  }, [ordering])

  // Handle filter clear
  const handleClearFilters = useCallback(() => {
    setSearch('')
    setStatusFilter('')
    setVisibilityFilter('')
    setDomainFilter('')
    setPage(1)
  }, [])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(search.trim() || statusFilter || visibilityFilter || domainFilter.trim())
  }, [search, statusFilter, visibilityFilter, domainFilter])

  // Table columns
  const columns: TableColumn<Asset>[] = useMemo(
    () => [
      {
        id: 'name',
        label: 'Name',
        sortable: true,
        accessor: (asset) => (
          <Box>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                cursor: 'pointer',
                '&:hover': { textDecoration: 'underline' },
              }}
              onClick={() => navigate(`/assets/${asset.id}`)}
            >
              {asset.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {asset.key}
            </Typography>
          </Box>
        ),
      },
      {
        id: 'domain',
        label: 'Domain',
        sortable: true,
        accessor: (asset) => asset.domain || (
          <Typography variant="body2" color="text.secondary">
            —
          </Typography>
        ),
      },
      {
        id: 'status',
        label: 'Status',
        sortable: true,
        accessor: (asset) => (
          <Chip
            label={asset.status}
            size="small"
            color={
              asset.status === 'ACTIVE'
                ? 'success'
                : asset.status === 'PUBLIC'
                ? 'info'
                : asset.status === 'DRAFT'
                ? 'default'
                : 'warning'
            }
            variant="outlined"
          />
        ),
      },
      {
        id: 'visibility',
        label: 'Visibility',
        sortable: true,
        accessor: (asset) => (
          <Chip
            label={asset.visibility}
            size="small"
            color={asset.visibility === 'PUBLIC' ? 'primary' : 'default'}
            variant="outlined"
          />
        ),
      },
      {
        id: 'dq_status',
        label: 'Data Quality',
        sortable: true,
        accessor: (asset) => (
          <Chip
            label={asset.dq_status}
            size="small"
            color={
              asset.dq_status === 'PASS'
                ? 'success'
                : asset.dq_status === 'WARN'
                ? 'warning'
                : asset.dq_status === 'FAIL'
                ? 'error'
                : 'default'
            }
            variant="outlined"
          />
        ),
      },
      {
        id: 'compliance_status',
        label: 'Compliance',
        sortable: true,
        accessor: (asset) => (
          <Chip
            label={asset.compliance_status}
            size="small"
            color={
              asset.compliance_status === 'PASS'
                ? 'success'
                : asset.compliance_status === 'WARN'
                ? 'warning'
                : asset.compliance_status === 'FAIL'
                ? 'error'
                : 'default'
            }
            variant="outlined"
          />
        ),
      },
      {
        id: 'created_at',
        label: 'Created',
        sortable: true,
        accessor: (asset) => (
          <Typography variant="body2" color="text.secondary">
            {formatDate(asset.created_at)}
          </Typography>
        ),
      },
    ],
    [navigate]
  )

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading assets..." />
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
            title="Failed to load assets"
            message={error.message || 'An error occurred while loading assets.'}
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
                Assets
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Manage your data assets
              </Typography>
            </Box>

            <NoResultsEmptyState
              title="No assets found"
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
              Assets
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Manage your data assets
            </Typography>
          </Box>

          <NoDataEmptyState
            title="No assets yet"
            description="Get started by creating your first data asset."
            primaryAction={{
              label: 'Create Asset',
              onClick: () => navigate('/assets/create'),
              primary: true,
            }}
          />
        </Box>
      </Container>
    )
  }

  // Main content - assets list
  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Assets
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Manage your data assets ({data.count} total)
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetch()} disabled={isFetching}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => navigate('/assets/create')}
            >
              Create Asset
            </Button>
          </Box>
        </Box>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Search */}
            <Box>
              <SearchBar
                value={search}
                onChange={(value) => {
                  setSearch(value)
                  setPage(1) // Reset to first page on search
                }}
                placeholder="Search assets by name, key, or description..."
                showClear
              />
            </Box>

            {/* Filter chips */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              <FilterListIcon sx={{ color: 'text.secondary' }} />
              <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
                Filters:
              </Typography>

              {/* Status filter */}
              <Chip
                label={`Status: ${statusFilter || 'All'}`}
                onClick={() => {
                  const statuses: (AssetStatus | '')[] = ['', 'DRAFT', 'ACTIVE', 'PUBLIC', 'RETIRED']
                  const currentIndex = statuses.indexOf(statusFilter)
                  const nextIndex = (currentIndex + 1) % statuses.length
                  setStatusFilter(statuses[nextIndex])
                  setPage(1)
                }}
                onDelete={statusFilter ? () => setStatusFilter('') : undefined}
                color={statusFilter ? 'primary' : 'default'}
                variant={statusFilter ? 'filled' : 'outlined'}
              />

              {/* Visibility filter */}
              <Chip
                label={`Visibility: ${visibilityFilter || 'All'}`}
                onClick={() => {
                  const visibilities: (AssetVisibility | '')[] = ['', 'INTERNAL', 'PUBLIC']
                  const currentIndex = visibilities.indexOf(visibilityFilter)
                  const nextIndex = (currentIndex + 1) % visibilities.length
                  setVisibilityFilter(visibilities[nextIndex])
                  setPage(1)
                }}
                onDelete={visibilityFilter ? () => setVisibilityFilter('') : undefined}
                color={visibilityFilter ? 'primary' : 'default'}
                variant={visibilityFilter ? 'filled' : 'outlined'}
              />

              {/* Domain filter */}
              {domainFilter && (
                <Chip
                  label={`Domain: ${domainFilter}`}
                  onDelete={() => {
                    setDomainFilter('')
                    setPage(1)
                  }}
                  color="primary"
                  variant="filled"
                />
              )}

              {hasActiveFilters && (
                <Button
                  size="small"
                  onClick={handleClearFilters}
                  sx={{ ml: 'auto' }}
                >
                  Clear All
                </Button>
              )}
            </Box>
          </Box>
        </Paper>

        {/* Assets Table */}
        <Paper>
          <Box sx={{ overflow: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '14px',
              }}
            >
              <thead>
                <tr
                  style={{
                    background: '#f5f5f5',
                    borderBottom: '1px solid #e0e0e0',
                  }}
                >
                  {columns.map((column) => {
                    const sortDirection = getSortState(column.id)
                    const isSortable = column.sortable !== false

                    return (
                      <th
                        key={column.id}
                        style={{
                          padding: '12px',
                          textAlign: 'left',
                          fontWeight: 500,
                          cursor: isSortable ? 'pointer' : 'default',
                          userSelect: 'none',
                        }}
                        onClick={() => isSortable && handleSort(column.id)}
                        onMouseEnter={(e) => {
                          if (isSortable) {
                            e.currentTarget.style.background = '#eeeeee'
                          }
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.background = '#f5f5f5'
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <span>{column.label}</span>
                          {isSortable && (
                            <TableSortIcon
                              direction={sortDirection}
                              isActive={!!sortDirection}
                              size="small"
                            />
                          )}
                        </Box>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {data.results.map((asset) => (
                  <tr
                    key={asset.id}
                    style={{
                      borderBottom: '1px solid #e0e0e0',
                      cursor: 'pointer',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#f5f5f5'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'transparent'
                    }}
                    onClick={() => navigate(`/assets/${asset.id}`)}
                  >
                    {columns.map((column) => (
                      <td key={column.id} style={{ padding: '12px' }}>
                        {column.accessor ? column.accessor(asset) : (asset as any)[column.id] || ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Box>

          {/* Pagination */}
          {data.total_pages > 1 && (
            <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
              <EnhancedPagination
                page={page}
                totalPages={data.total_pages}
                onPageChange={setPage}
                pageSize={pageSize}
                onPageSizeChange={(newSize) => {
                  setPageSize(newSize)
                  setPage(1) // Reset to first page when changing page size
                }}
                totalItems={data.count}
                pageSizeOptions={[10, 20, 50, 100]}
              />
            </Box>
          )}
        </Paper>
      </Box>
    </Container>
  )
}

