/**
 * DataQualityRunList Component
 *
 * Reusable component for displaying a list of data quality runs with filtering, sorting, and pagination.
 * Shows run cards with status, quality score, and basic information.
 */

import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  Paper,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material'
import { useDQRuns } from '@/hooks/useDQRuns'
import type { DQRun, DQRunStatus } from '@/lib/api/data-quality'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { formatDistanceToNow } from 'date-fns'

export interface DataQualityRunListProps {
  /**
   * Filter by asset ID
   */
  assetId?: string
  /**
   * Filter by dataset ID
   */
  datasetId?: string
  /**
   * Show filters
   * @default true
   */
  showFilters?: boolean
  /**
   * Custom page size
   * @default 20
   */
  pageSize?: number
  /**
   * Callback when run is clicked
   */
  onRunClick?: (run: DQRun) => void
}

/**
 * Get run status badge color
 */
function getStatusBadgeColor(status: DQRunStatus): 'success' | 'warning' | 'error' | 'info' {
  switch (status) {
    case 'SUCCEEDED':
      return 'success'
    case 'RUNNING':
    case 'PENDING':
      return 'info'
    case 'FAILED':
      return 'error'
    default:
      return 'info'
  }
}

/**
 * Get overall status badge color
 */
function getOverallStatusBadgeColor(status?: string | null): 'success' | 'warning' | 'error' | 'default' {
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    default:
      return 'default'
  }
}

/**
 * Get quality score color
 */
function getScoreColor(score?: number | null): 'success' | 'warning' | 'error' {
  if (!score) return 'error'
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'error'
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

/**
 * DataQualityRunList Component
 *
 * @example
 * ```tsx
 * <DataQualityRunList assetId="asset-123" />
 * ```
 */
export const DataQualityRunList: React.FC<DataQualityRunListProps> = ({
  assetId,
  datasetId,
  showFilters = true,
  pageSize = 20,
  onRunClick,
}) => {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [currentPageSize, setCurrentPageSize] = useState(pageSize)
  const [statusFilter, setStatusFilter] = useState<DQRunStatus | ''>('')

  // Fetch DQ runs
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useDQRuns({
    page,
    page_size: currentPageSize,
    ordering: '-created_at',
    asset_id: assetId,
    dataset_id: datasetId,
    status: statusFilter || undefined,
  })

  // Handle run click
  const handleRunClick = useCallback(
    (run: DQRun) => {
      if (onRunClick) {
        onRunClick(run)
      } else {
        navigate(`/data-quality/runs/${run.id}`)
      }
    },
    [navigate, onRunClick]
  )

  // Loading state
  if (isLoading) {
    return (
      <Box>
        <LoadingState message="Loading data quality runs..." />
      </Box>
    )
  }

  // Error state
  if (error) {
    return (
      <ErrorState
        title="Failed to load data quality runs"
        message={error.message || 'An error occurred while loading data quality runs.'}
        onRetry={() => refetch()}
      />
    )
  }

  // Empty state
  if (!data || data.results.length === 0) {
    return (
      <Box>
        {showFilters && (
          <Paper sx={{ p: 2, mb: 2 }}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Status</InputLabel>
                <Select
                  value={statusFilter}
                  label="Status"
                  onChange={(e) => {
                    setStatusFilter(e.target.value as DQRunStatus | '')
                    setPage(1)
                  }}
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  <MenuItem value="PENDING">Pending</MenuItem>
                  <MenuItem value="RUNNING">Running</MenuItem>
                  <MenuItem value="SUCCEEDED">Succeeded</MenuItem>
                  <MenuItem value="FAILED">Failed</MenuItem>
                </Select>
              </FormControl>
              <Tooltip title="Refresh">
                <IconButton onClick={() => refetch()} disabled={isFetching}>
                  <RefreshIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Paper>
        )}
        <NoDataEmptyState
          title="No Data Quality Runs"
          message="No data quality runs found. Create a new run to get started."
        />
      </Box>
    )
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h5">Data Quality Runs</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {showFilters && (
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetch()} disabled={isFetching}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* Filters */}
      {showFilters && (
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value as DQRunStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="PENDING">Pending</MenuItem>
                <MenuItem value="RUNNING">Running</MenuItem>
                <MenuItem value="SUCCEEDED">Succeeded</MenuItem>
                <MenuItem value="FAILED">Failed</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Paper>
      )}

      {/* Run List */}
      <Grid container spacing={2}>
        {data.results.map((run) => (
          <Grid item xs={12} key={run.id}>
            <Paper
              sx={{
                p: 2,
                cursor: 'pointer',
                '&:hover': {
                  boxShadow: 3,
                },
              }}
              onClick={() => handleRunClick(run)}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    {run.profile_key}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {run.asset ? `Asset: ${run.asset}` : run.dataset ? `Dataset: ${run.dataset}` : 'File-based'}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Chip
                    label={run.status}
                    size="small"
                    color={getStatusBadgeColor(run.status)}
                  />
                  {run.overall_status && (
                    <Chip
                      label={run.overall_status}
                      size="small"
                      color={getOverallStatusBadgeColor(run.overall_status)}
                    />
                  )}
                  {run.quality_score !== null && run.quality_score !== undefined && (
                    <Chip
                      label={`Score: ${run.quality_score.toFixed(1)}`}
                      size="small"
                      color={getScoreColor(run.quality_score)}
                    />
                  )}
                </Box>
              </Box>
              <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Engine: {run.engine}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Created: {formatDate(run.created_at)}
                </Typography>
                {run.completed_at && (
                  <Typography variant="body2" color="text.secondary">
                    Completed: {formatDate(run.completed_at)}
                  </Typography>
                )}
              </Box>
            </Paper>
          </Grid>
        ))}
      </Grid>

      {/* Pagination */}
      {data.count > currentPageSize && (
        <Box sx={{ mt: 3 }}>
          <EnhancedPagination
            count={data.count}
            page={page}
            pageSize={currentPageSize}
            onPageChange={setPage}
            onPageSizeChange={(newSize) => {
              setCurrentPageSize(newSize)
              setPage(1)
            }}
          />
        </Box>
      )}
    </Box>
  )
}

