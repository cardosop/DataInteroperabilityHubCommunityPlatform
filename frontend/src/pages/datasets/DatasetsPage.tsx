/**
 * Datasets Page
 *
 * Comprehensive dataset list page with:
 * - Dataset list with server-side pagination
 * - Search and filtering
 * - Sorting
 * - Dataset version display
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
  Menu,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
} from '@mui/material'
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  FilterList as FilterListIcon,
  Visibility as VisibilityIcon,
  Storage as StorageIcon,
} from '@mui/icons-material'
import { useDatasets, type Dataset } from '@/hooks/useDatasets'
import type { DatasetFormat } from '@/lib/api/datasets'
import { EnhancedTable, type TableColumn } from '@/components/data-display/Table'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { SearchBar } from '@/components/forms/SearchBar'
import { TableSortIcon } from '@/components/data-display/Table/TableSortIcon'

/**
 * Date formatting utility
 */
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
 * Format file size
 */
const formatFileSize = (bytes: number | null | undefined): string => {
  if (!bytes) return 'N/A'
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  if (bytes === 0) return '0 Bytes'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
}

/**
 * Get format badge color
 */
const getFormatColor = (format: DatasetFormat): 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' => {
  switch (format) {
    case 'CSV':
      return 'primary'
    case 'JSON':
      return 'secondary'
    case 'PARQUET':
      return 'success'
    default:
      return 'default'
  }
}

/**
 * Datasets Page Component
 */
export const DatasetsPage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Search and filter state
  const [search, setSearch] = useState<string>('')
  const [formatFilter, setFormatFilter] = useState<DatasetFormat | ''>('')
  const [assetIdFilter, setAssetIdFilter] = useState<string>('')

  // Sorting state
  const [ordering, setOrdering] = useState<string>('-created_at')

  // Filter menu state
  const [filterAnchorEl, setFilterAnchorEl] = useState<null | HTMLElement>(null)
  const filterMenuOpen = Boolean(filterAnchorEl)

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
    if (formatFilter) {
      params.format = formatFilter
    }
    if (assetIdFilter.trim()) {
      params.asset_id = assetIdFilter.trim()
    }

    return params
  }, [page, pageSize, ordering, search, formatFilter, assetIdFilter])

  // Fetch datasets
  const { data, isLoading, error, refetch, isFetching } = useDatasets(queryParams)

  // Handle search
  const handleSearch = useCallback((value: string) => {
    setSearch(value)
    setPage(1) // Reset to first page on new search
  }, [])

  // Handle filter changes
  const handleFormatFilterChange = useCallback((value: DatasetFormat | '') => {
    setFormatFilter(value)
    setPage(1) // Reset to first page on filter change
  }, [])

  const handleAssetIdFilterChange = useCallback((value: string) => {
    setAssetIdFilter(value)
    setPage(1) // Reset to first page on filter change
  }, [])

  // Handle sorting
  const handleSort = useCallback((field: string) => {
    const currentOrdering = ordering.split(',')[0]
    const currentField = currentOrdering.replace('-', '')
    const currentDirection = currentOrdering.startsWith('-') ? 'desc' : 'asc'

    let newOrdering: string
    if (currentField === field) {
      // Toggle direction
      newOrdering = currentDirection === 'asc' ? `-${field}` : field
    } else {
      // New field, default to descending
      newOrdering = `-${field}`
    }

    setOrdering(newOrdering)
    setPage(1) // Reset to first page on sort change
  }, [ordering])

  // Handle pagination
  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage)
  }, [])

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(1) // Reset to first page on page size change
  }, [])

  // Clear filters
  const handleClearFilters = useCallback(() => {
    setSearch('')
    setFormatFilter('')
    setAssetIdFilter('')
    setPage(1)
    setFilterAnchorEl(null)
  }, [])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!search || !!formatFilter || !!assetIdFilter
  }, [search, formatFilter, assetIdFilter])

  // Table columns
  const columns: TableColumn<Dataset>[] = useMemo(
    () => [
      {
        id: 'id',
        label: 'ID',
        minWidth: 100,
        accessor: (dataset) => (
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
            {dataset.id.substring(0, 8)}...
          </Typography>
        ),
      },
      {
        id: 'format',
        label: 'Format',
        minWidth: 100,
        accessor: (dataset) => (
          <Chip
            label={dataset.format}
            size="small"
            color={getFormatColor(dataset.format)}
            variant="outlined"
          />
        ),
      },
      {
        id: 'version',
        label: 'Version',
        minWidth: 120,
        accessor: (dataset) => (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" fontWeight={500}>
              v{dataset.version}
            </Typography>
            {dataset.is_current && (
              <Chip label="Current" size="small" color="primary" variant="outlined" />
            )}
            {dataset.semantic_version && (
              <Chip
                label={dataset.semantic_version}
                size="small"
                variant="outlined"
                sx={{ fontFamily: 'monospace' }}
              />
            )}
            {dataset.version_tags && dataset.version_tags.length > 0 && (
              <Tooltip title={dataset.version_tags.join(', ')}>
                <Chip
                  label={`${dataset.version_tags.length} tag${dataset.version_tags.length !== 1 ? 's' : ''}`}
                  size="small"
                  variant="outlined"
                />
              </Tooltip>
            )}
          </Box>
        ),
      },
      {
        id: 'row_count',
        label: 'Rows',
        minWidth: 100,
        align: 'right',
        accessor: (dataset) => (
          <Typography variant="body2">
            {dataset.row_count !== null && dataset.row_count !== undefined
              ? dataset.row_count.toLocaleString()
              : 'N/A'}
          </Typography>
        ),
      },
      {
        id: 'asset',
        label: 'Asset',
        minWidth: 150,
        accessor: (dataset) => (
          <Typography variant="body2" color={dataset.asset ? 'text.primary' : 'text.secondary'}>
            {dataset.asset ? dataset.asset.substring(0, 8) + '...' : 'No asset'}
          </Typography>
        ),
      },
      {
        id: 'created_at',
        label: 'Created',
        minWidth: 150,
        sortable: true,
        accessor: (dataset) => (
          <Typography variant="body2" color="text.secondary">
            {formatDate(dataset.created_at)}
          </Typography>
        ),
      },
      {
        id: 'actions',
        label: 'Actions',
        minWidth: 100,
        align: 'right',
        accessor: (dataset) => (
          <Tooltip title="View dataset">
            <IconButton
              size="small"
              onClick={() => navigate(`/datasets/${dataset.id}`)}
              aria-label={`View dataset ${dataset.id}`}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
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
          <LoadingState message="Loading datasets..." />
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
            title="Failed to load datasets"
            message={error.message || 'An error occurred while loading datasets.'}
            onRetry={() => refetch()}
          />
        </Box>
      </Container>
    )
  }

  const datasets = data?.results || []
  const totalCount = data?.count || 0
  const totalPages = Math.ceil(totalCount / pageSize)

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Datasets
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {totalCount} dataset{totalCount !== 1 ? 's' : ''} total
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={() => refetch()}
              disabled={isFetching}
            >
              Refresh
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => navigate('/datasets/new')}
            >
              Upload Dataset
            </Button>
          </Box>
        </Box>

        {/* Search and Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            <Box sx={{ flex: 1, minWidth: 300 }}>
              <SearchBar
                value={search}
                onChange={handleSearch}
                placeholder="Search datasets..."
                debounceMs={300}
              />
            </Box>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Format</InputLabel>
              <Select
                value={formatFilter}
                label="Format"
                onChange={(e) => handleFormatFilterChange(e.target.value as DatasetFormat | '')}
              >
                <MenuItem value="">All Formats</MenuItem>
                <MenuItem value="CSV">CSV</MenuItem>
                <MenuItem value="JSON">JSON</MenuItem>
                <MenuItem value="PARQUET">Parquet</MenuItem>
              </Select>
            </FormControl>

            {hasActiveFilters && (
              <Button
                variant="outlined"
                size="small"
                onClick={handleClearFilters}
              >
                Clear Filters
              </Button>
            )}
          </Box>
        </Paper>

        {/* Datasets Table */}
        {datasets.length === 0 ? (
          <Paper sx={{ p: 4 }}>
            {hasActiveFilters ? (
              <NoResultsEmptyState
                title="No datasets found"
                description="Try adjusting your search or filters."
                onClearFilters={handleClearFilters}
              />
            ) : (
              <NoDataEmptyState
                title="No datasets"
                description="Get started by uploading your first dataset."
                primaryAction={{
                  label: 'Upload Dataset',
                  onClick: () => navigate('/datasets/new'),
                }}
              />
            )}
          </Paper>
        ) : (
          <>
            <Paper>
              <EnhancedTable
                columns={columns}
                data={datasets}
                onSort={handleSort}
                currentSort={ordering}
                loading={isFetching}
                emptyMessage="No datasets found"
              />
            </Paper>

            {/* Pagination */}
            {totalPages > 1 && (
              <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
                <EnhancedPagination
                  currentPage={page}
                  totalPages={totalPages}
                  pageSize={pageSize}
                  totalItems={totalCount}
                  onPageChange={handlePageChange}
                  onPageSizeChange={handlePageSizeChange}
                  pageSizeOptions={[10, 20, 50, 100]}
                />
              </Box>
            )}
          </>
        )}
      </Box>
    </Container>
  )
}

