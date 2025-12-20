/**
 * Contracts Page
 *
 * Comprehensive contract list page with:
 * - Contract list with server-side pagination
 * - Search and filtering
 * - Sorting
 * - Contract status badges
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
import { useContracts } from '@/hooks/useContracts'
import { useRealtimeContracts } from '@/hooks/useRealtimeContracts'
import type { Contract, ContractStatus, NormalizationStatus, ValidationStatus } from '@/lib/api/contracts'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { SearchBar } from '@/components/forms/SearchBar'
import { TableSortIcon } from '@/components/data-display/Table/TableSortIcon'
import { Badge } from '@/components/data-display/Badge'

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
 * Get contract name from hub_contract_json
 */
const getContractName = (contract: Contract): string => {
  return (
    contract.hub_contract_json?.info?.name ||
    contract.hub_contract_json?.id ||
    'Unnamed Contract'
  )
}

/**
 * Get contract status badge variant
 */
const getStatusBadgeVariant = (status: ContractStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' => {
  switch (status) {
    case 'ACTIVE':
      return 'success'
    case 'DRAFT':
      return 'info'
    case 'RETIRED':
      return 'neutral'
    default:
      return 'neutral'
  }
}

/**
 * Get normalization status badge variant
 */
const getNormalizationStatusBadgeVariant = (
  status: NormalizationStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' => {
  switch (status) {
    case 'NORMALIZED_OK':
      return 'success'
    case 'NORMALIZED_WITH_WARNINGS':
      return 'warning'
    case 'NORMALIZATION_FAILED':
      return 'error'
    case 'NOT_NORMALIZED':
      return 'neutral'
    default:
      return 'neutral'
  }
}

/**
 * Get validation status badge variant
 */
const getValidationStatusBadgeVariant = (
  status?: ValidationStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' => {
  if (!status) return 'neutral'
  switch (status) {
    case 'VALID':
      return 'success'
    case 'WARNING_ONLY':
      return 'warning'
    case 'INVALID':
    case 'ERROR':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Contracts Page Component
 */
export const ContractsPage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Filter state (only filters supported by API)
  const [ownerNameFilter, setOwnerNameFilter] = useState<string>('')
  const [ownerEmailFilter, setOwnerEmailFilter] = useState<string>('')
  const [tagFilter, setTagFilter] = useState<string>('')
  const [complianceRegimeFilter, setComplianceRegimeFilter] = useState<string>('')
  const [qualityProfileFilter, setQualityProfileFilter] = useState<string>('')

  // Sorting state
  const [ordering, setOrdering] = useState<string>('-created_at')

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: Record<string, any> = {
      page,
      page_size: pageSize,
      ordering,
    }

    if (ownerNameFilter.trim()) {
      params.owner_name = ownerNameFilter.trim()
    }
    if (ownerEmailFilter.trim()) {
      params.owner_email = ownerEmailFilter.trim()
    }
    if (tagFilter.trim()) {
      params.tag = tagFilter.trim()
    }
    if (complianceRegimeFilter.trim()) {
      params.compliance_regime = complianceRegimeFilter.trim()
    }
    if (qualityProfileFilter.trim()) {
      params.quality_profile = qualityProfileFilter.trim()
    }

    return params
  }, [
    page,
    pageSize,
    ordering,
    ownerNameFilter,
    ownerEmailFilter,
    tagFilter,
    complianceRegimeFilter,
    qualityProfileFilter,
  ])

  // Fetch contracts
  const { data, isLoading, error, refetch, isFetching } = useContracts(queryParams)

  // Subscribe to real-time contract updates
  useRealtimeContracts({
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
  const getSortState = useCallback(
    (columnId: string): 'asc' | 'desc' | null => {
      const currentColumn = ordering.startsWith('-') ? ordering.slice(1) : ordering
      if (currentColumn !== columnId) return null
      return ordering.startsWith('-') ? 'desc' : 'asc'
    },
    [ordering]
  )

  // Handle filter clear
  const handleClearFilters = useCallback(() => {
    setOwnerNameFilter('')
    setOwnerEmailFilter('')
    setTagFilter('')
    setComplianceRegimeFilter('')
    setQualityProfileFilter('')
    setPage(1)
  }, [])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(
      ownerNameFilter.trim() ||
      ownerEmailFilter.trim() ||
      tagFilter.trim() ||
      complianceRegimeFilter.trim() ||
      qualityProfileFilter.trim()
    )
  }, [ownerNameFilter, ownerEmailFilter, tagFilter, complianceRegimeFilter, qualityProfileFilter])

  // Table columns
  const columns = useMemo(
    () => [
      {
        id: 'name',
        label: 'Contract Name',
        sortable: true,
        accessor: (contract: Contract) => (
          <Box>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                cursor: 'pointer',
                '&:hover': { textDecoration: 'underline' },
              }}
              onClick={() => navigate(`/contracts/${contract.id}`)}
            >
              {getContractName(contract)}
            </Typography>
            {contract.hub_contract_json?.id && (
              <Typography variant="caption" color="text.secondary">
                ID: {contract.hub_contract_json.id}
              </Typography>
            )}
          </Box>
        ),
      },
      {
        id: 'status',
        label: 'Status',
        sortable: true,
        accessor: (contract: Contract) => (
          <Badge variant={getStatusBadgeVariant(contract.status)} size="sm">
            {contract.status}
          </Badge>
        ),
      },
      {
        id: 'normalization_status',
        label: 'Normalization',
        sortable: true,
        accessor: (contract: Contract) => (
          <Badge variant={getNormalizationStatusBadgeVariant(contract.normalization_status)} size="sm">
            {contract.normalization_status.replace(/_/g, ' ')}
          </Badge>
        ),
      },
      {
        id: 'validation_status',
        label: 'Validation',
        sortable: true,
        accessor: (contract: Contract) => {
          if (!contract.validation_status) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            )
          }
          return (
            <Badge variant={getValidationStatusBadgeVariant(contract.validation_status)} size="sm">
              {contract.validation_status}
            </Badge>
          )
        },
      },
      {
        id: 'tags',
        label: 'Tags',
        sortable: false,
        accessor: (contract: Contract) => {
          const tags = contract.tags || contract.hub_contract_json?.info?.tags || []
          if (tags.length === 0) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            )
          }
          return (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {tags.slice(0, 3).map((tag, index) => (
                <Chip key={index} label={tag} size="small" variant="outlined" />
              ))}
              {tags.length > 3 && (
                <Chip label={`+${tags.length - 3}`} size="small" variant="outlined" />
              )}
            </Box>
          )
        },
      },
      {
        id: 'owners',
        label: 'Owners',
        sortable: false,
        accessor: (contract: Contract) => {
          const owners = contract.owners || contract.hub_contract_json?.info?.owners || []
          if (owners.length === 0) {
            return (
              <Typography variant="body2" color="text.secondary">
                —
              </Typography>
            )
          }
          return (
            <Box>
              {owners.slice(0, 2).map((owner, index) => (
                <Typography key={index} variant="body2">
                  {owner.name || owner.email}
                </Typography>
              ))}
              {owners.length > 2 && (
                <Typography variant="caption" color="text.secondary">
                  +{owners.length - 2} more
                </Typography>
              )}
            </Box>
          )
        },
      },
      {
        id: 'created_at',
        label: 'Created',
        sortable: true,
        accessor: (contract: Contract) => (
          <Typography variant="body2" color="text.secondary">
            {formatDate(contract.created_at)}
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
                Contracts
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Manage your data contracts
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
              Contracts
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Manage your data contracts
            </Typography>
          </Box>

          <NoDataEmptyState
            title="No contracts yet"
            description="Get started by creating your first data contract."
            primaryAction={{
              label: 'Create Contract',
              onClick: () => navigate('/contracts/create'),
              primary: true,
            }}
          />
        </Box>
      </Container>
    )
  }

  // Main content - contracts list
  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Contracts
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Manage your data contracts ({data.count} total)
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
              onClick={() => navigate('/contracts/create')}
            >
              Create Contract
            </Button>
          </Box>
        </Box>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Search by owner name */}
            <Box>
              <SearchBar
                value={ownerNameFilter}
                onChange={(value) => {
                  setOwnerNameFilter(value)
                  setPage(1) // Reset to first page on filter change
                }}
                placeholder="Search by owner name..."
                showClear
              />
            </Box>

            {/* Filter chips */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
              <FilterListIcon sx={{ color: 'text.secondary' }} />
              <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
                Filters:
              </Typography>

              {/* Owner email filter */}
              {ownerEmailFilter && (
                <Chip
                  label={`Owner Email: ${ownerEmailFilter}`}
                  onDelete={() => {
                    setOwnerEmailFilter('')
                    setPage(1)
                  }}
                  color="primary"
                  variant="filled"
                />
              )}

              {/* Tag filter */}
              {tagFilter && (
                <Chip
                  label={`Tag: ${tagFilter}`}
                  onDelete={() => {
                    setTagFilter('')
                    setPage(1)
                  }}
                  color="primary"
                  variant="filled"
                />
              )}

              {/* Compliance regime filter */}
              {complianceRegimeFilter && (
                <Chip
                  label={`Compliance: ${complianceRegimeFilter}`}
                  onDelete={() => {
                    setComplianceRegimeFilter('')
                    setPage(1)
                  }}
                  color="primary"
                  variant="filled"
                />
              )}

              {/* Quality profile filter */}
              {qualityProfileFilter && (
                <Chip
                  label={`Quality Profile: ${qualityProfileFilter}`}
                  onDelete={() => {
                    setQualityProfileFilter('')
                    setPage(1)
                  }}
                  color="primary"
                  variant="filled"
                />
              )}

              {hasActiveFilters && (
                <Button size="small" onClick={handleClearFilters} sx={{ ml: 'auto' }}>
                  Clear All
                </Button>
              )}
            </Box>
          </Box>
        </Paper>

        {/* Contracts Table */}
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
                {data.results.map((contract) => (
                  <tr
                    key={contract.id}
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
                    onClick={() => navigate(`/contracts/${contract.id}`)}
                  >
                    {columns.map((column) => (
                      <td key={column.id} style={{ padding: '12px' }}>
                        {column.accessor ? column.accessor(contract) : (contract as any)[column.id] || ''}
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

