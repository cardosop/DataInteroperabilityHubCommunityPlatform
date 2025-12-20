/**
 * JobList Component
 *
 * Reusable component for displaying a list of jobs with filtering, sorting, and pagination.
 * Shows job cards with status, progress, and basic information.
 */

import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  Paper,
  Grid,
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
import { useJobs } from '@/hooks/useJobs'
import type { Job, JobStatus, JobType } from '@/lib/api/jobs'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { JobCard } from '../JobCard'

export interface JobListProps {
  /**
   * Filter by job type
   */
  jobType?: JobType
  /**
   * Filter by resource type
   */
  resourceType?: string
  /**
   * Filter by resource ID
   */
  resourceId?: string
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
   * Callback when job is clicked
   */
  onJobClick?: (job: Job) => void
}

/**
 * JobList Component
 *
 * @example
 * ```tsx
 * <JobList jobType="DQ_RUN" />
 * ```
 */
export const JobList: React.FC<JobListProps> = ({
  jobType,
  resourceType,
  resourceId,
  showFilters = true,
  pageSize = 20,
  onJobClick,
}) => {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [currentPageSize, setCurrentPageSize] = useState(pageSize)
  const [statusFilter, setStatusFilter] = useState<JobStatus | ''>('')
  const [typeFilter, setTypeFilter] = useState<JobType | ''>(jobType || '')

  // Fetch jobs
  const {
    data,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useJobs({
    page,
    page_size: currentPageSize,
    ordering: '-created_at',
    type: typeFilter || jobType || undefined,
    status: statusFilter || undefined,
  })

  // Handle job click
  const handleJobClick = useCallback(
    (job: Job) => {
      if (onJobClick) {
        onJobClick(job)
      } else {
        navigate(`/jobs/${job.id}`)
      }
    },
    [navigate, onJobClick]
  )

  // Loading state
  if (isLoading) {
    return (
      <Box>
        <LoadingState message="Loading jobs..." />
      </Box>
    )
  }

  // Error state
  if (error) {
    return (
      <ErrorState
        title="Failed to load jobs"
        message={error.message || 'An error occurred while loading jobs.'}
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
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Type</InputLabel>
                <Select
                  value={typeFilter}
                  label="Type"
                  onChange={(e) => {
                    setTypeFilter(e.target.value as JobType | '')
                    setPage(1)
                  }}
                >
                  <MenuItem value="">All Types</MenuItem>
                  <MenuItem value="DQ_RUN">Data Quality Run</MenuItem>
                  <MenuItem value="COMPLIANCE_RUN">Compliance Run</MenuItem>
                  <MenuItem value="CONTRACT_VALIDATION">Contract Validation</MenuItem>
                  <MenuItem value="SEMANTIC_MAPPING">Semantic Mapping</MenuItem>
                  <MenuItem value="CONTRACT_MIGRATION">Contract Migration</MenuItem>
                  <MenuItem value="SCHEDULED_INGESTION">Scheduled Ingestion</MenuItem>
                  <MenuItem value="RETENTION_POLICY_ENFORCEMENT">Retention Policy Enforcement</MenuItem>
                  <MenuItem value="SEARCH_INDEX_UPDATE">Search Index Update</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Status</InputLabel>
                <Select
                  value={statusFilter}
                  label="Status"
                  onChange={(e) => {
                    setStatusFilter(e.target.value as JobStatus | '')
                    setPage(1)
                  }}
                >
                  <MenuItem value="">All Statuses</MenuItem>
                  <MenuItem value="PENDING">Pending</MenuItem>
                  <MenuItem value="RUNNING">Running</MenuItem>
                  <MenuItem value="COMPLETED">Completed</MenuItem>
                  <MenuItem value="FAILED">Failed</MenuItem>
                  <MenuItem value="CANCELLED">Cancelled</MenuItem>
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
          title="No Jobs Found"
          message="No jobs found matching the current filters."
        />
      </Box>
    )
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h5">Jobs</Typography>
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
              <InputLabel>Type</InputLabel>
              <Select
                value={typeFilter}
                label="Type"
                onChange={(e) => {
                  setTypeFilter(e.target.value as JobType | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">All Types</MenuItem>
                <MenuItem value="DQ_RUN">Data Quality Run</MenuItem>
                <MenuItem value="COMPLIANCE_RUN">Compliance Run</MenuItem>
                <MenuItem value="CONTRACT_VALIDATION">Contract Validation</MenuItem>
                <MenuItem value="SEMANTIC_MAPPING">Semantic Mapping</MenuItem>
                <MenuItem value="CONTRACT_MIGRATION">Contract Migration</MenuItem>
                <MenuItem value="SCHEDULED_INGESTION">Scheduled Ingestion</MenuItem>
                <MenuItem value="RETENTION_POLICY_ENFORCEMENT">Retention Policy Enforcement</MenuItem>
                <MenuItem value="SEARCH_INDEX_UPDATE">Search Index Update</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value as JobStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="PENDING">Pending</MenuItem>
                <MenuItem value="RUNNING">Running</MenuItem>
                <MenuItem value="COMPLETED">Completed</MenuItem>
                <MenuItem value="FAILED">Failed</MenuItem>
                <MenuItem value="CANCELLED">Cancelled</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Paper>
      )}

      {/* Job List */}
      <Grid container spacing={2}>
        {data.results.map((job) => (
          <Grid item xs={12} sm={6} md={4} key={job.id}>
            <JobCard job={job} onClick={handleJobClick} />
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

