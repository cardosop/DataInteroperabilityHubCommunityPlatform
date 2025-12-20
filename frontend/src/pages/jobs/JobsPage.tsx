/**
 * Jobs Page
 *
 * Comprehensive job list page with:
 * - Job list with server-side pagination
 * - Search and filtering (by type, status)
 * - Job status badges
 * - Job cancellation functionality
 * - Empty state
 * - Loading state
 * - Error state
 */

import React, { useState, useMemo, useCallback, useRef } from 'react'
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
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Alert,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Cancel as CancelIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material'
import { useJobs } from '@/hooks/useJobs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { Job, JobType, JobStatus } from '@/lib/api/jobs'
import { canCancelJob, isJobTerminal } from '@/lib/api/jobs'
import { queryKeys } from '@/lib/api/react-query'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import { SearchBar } from '@/components/forms/SearchBar'
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material'
import { formatDistanceToNow } from 'date-fns'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WebSocketEvent } from '@/lib/api/websocket-events'
import { useCallback, useEffect } from 'react'

/**
 * Get job status badge variant
 */
function getJobStatusBadgeVariant(status: JobStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'RUNNING':
      return 'info'
    case 'PENDING':
      return 'warning'
    case 'FAILED':
      return 'error'
    case 'CANCELLED':
      return 'neutral'
    default:
      return 'neutral'
  }
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
 * Format job type for display
 */
function formatJobType(type: JobType): string {
  return type
    .split('_')
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(' ')
}

/**
 * Jobs Page Component
 */
export const JobsPage: React.FC = () => {
  const navigate = useNavigate()
  const { showToast } = useToastManager()
  const queryClient = useQueryClient()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Search and filter state
  const [search, setSearch] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<JobStatus | ''>('')
  const [typeFilter, setTypeFilter] = useState<JobType | ''>('')

  // Sorting state
  const [ordering, setOrdering] = useState<string>('-created_at')

  // Cancel dialog state
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)
  const [jobToCancel, setJobToCancel] = useState<Job | null>(null)

  // Track processed job events to avoid duplicate notifications
  const processedEventsRef = useRef<Set<string>>(new Set())

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
    if (typeFilter) {
      params.type = typeFilter
    }

    return params
  }, [page, pageSize, ordering, search, statusFilter, typeFilter])

  // Fetch jobs
  const { data, isLoading, error, refetch, isFetching } = useJobs(queryParams)

  // Handle WebSocket events for real-time job updates
  const handleJobEvent = useCallback(
    (event: WebSocketEvent) => {
      // Only process job events
      if (!event.event_type.startsWith('job.')) {
        return
      }

      const eventId = `${event.event_type}-${event.data?.job_id}-${event.timestamp}`

      // Skip if we've already processed this event
      if (processedEventsRef.current.has(eventId)) {
        return
      }
      processedEventsRef.current.add(eventId)

      // Clean up old events (keep last 1000)
      if (processedEventsRef.current.size > 1000) {
        const eventsArray = Array.from(processedEventsRef.current)
        processedEventsRef.current = new Set(eventsArray.slice(-500))
      }

      const jobId = event.data?.job_id
      if (!jobId) {
        return
      }

      // Invalidate job queries to trigger refetch
      queryClient.invalidateQueries({
        queryKey: queryKeys.jobs.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.jobs.detail(jobId),
      })

      // Show notifications for job completion/failure
      if (event.event_type === 'job.completed') {
        const jobType = event.data?.job_type || 'Job'
        showToast({
          message: `${jobType} completed successfully`,
          severity: 'success',
        })
      } else if (event.event_type === 'job.failed') {
        const jobType = event.data?.job_type || 'Job'
        const errorMessage = event.data?.error_message || 'Unknown error'
        showToast({
          message: `${jobType} failed: ${errorMessage}`,
          severity: 'error',
        })
      } else if (event.event_type === 'job.cancelled') {
        const jobType = event.data?.job_type || 'Job'
        showToast({
          message: `${jobType} was cancelled`,
          severity: 'info',
        })
      }
    },
    [queryClient, showToast]
  )

  // Subscribe to job events via WebSocket
  const { isConnected: isWebSocketConnected } = useWebSocket(
    ['job.started', 'job.completed', 'job.failed', 'job.cancelled'],
    handleJobEvent
  )

  // Cancel job mutation
  const cancelJobMutation = useMutation({
    mutationFn: async (jobId: string) => {
      const response = await apiClient.post<Job>(`/api/v1/jobs/jobs/${jobId}/cancel/`)
      return response.data
    },
    onSuccess: (data) => {
      // Invalidate jobs list to refetch
      queryClient.invalidateQueries({
        queryKey: queryKeys.jobs.lists(),
      })

      // Update the specific job in cache
      queryClient.setQueryData(queryKeys.jobs.detail(data.id), data)

      showToast({
        message: 'Job cancelled successfully',
        severity: 'success',
      })

      setCancelDialogOpen(false)
      setJobToCancel(null)
    },
    onError: (error: Error) => {
      showToast({
        message: error.message || 'Failed to cancel job',
        severity: 'error',
      })
    },
  })

  // Handle cancel job
  const handleCancelClick = useCallback((job: Job) => {
    setJobToCancel(job)
    setCancelDialogOpen(true)
  }, [])

  // Handle confirm cancel
  const handleConfirmCancel = useCallback(() => {
    if (jobToCancel) {
      cancelJobMutation.mutate(jobToCancel.id)
    }
  }, [jobToCancel, cancelJobMutation])

  // Handle filter clear
  const handleClearFilters = useCallback(() => {
    setSearch('')
    setStatusFilter('')
    setTypeFilter('')
    setPage(1)
  }, [])

  // Check if any filters are active
  const hasActiveFilters = useMemo(() => {
    return !!(search.trim() || statusFilter || typeFilter)
  }, [search, statusFilter, typeFilter])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading jobs..." />
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
            title="Failed to load jobs"
            message={error.message || 'An error occurred while loading jobs.'}
            onRetry={() => refetch()}
          />
        </Box>
      </Container>
    )
  }

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Jobs
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Monitor and manage background jobs
              {isWebSocketConnected && (
                <Chip
                  label="Real-time updates active"
                  size="small"
                  color="success"
                  sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
                />
              )}
            </Typography>
          </Box>
          <Tooltip title="Refresh">
            <IconButton onClick={() => refetch()} disabled={isFetching}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <Box sx={{ flex: 1, minWidth: 200 }}>
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search jobs..."
                onClear={() => {
                  setSearch('')
                  setPage(1)
                }}
              />
            </Box>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value as JobStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All Statuses</em>
                </MenuItem>
                <MenuItem value="PENDING">Pending</MenuItem>
                <MenuItem value="RUNNING">Running</MenuItem>
                <MenuItem value="COMPLETED">Completed</MenuItem>
                <MenuItem value="FAILED">Failed</MenuItem>
                <MenuItem value="CANCELLED">Cancelled</MenuItem>
              </Select>
            </FormControl>

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
                <MenuItem value="">
                  <em>All Types</em>
                </MenuItem>
                <MenuItem value="DQ_RUN">DQ Run</MenuItem>
                <MenuItem value="COMPLIANCE_RUN">Compliance Run</MenuItem>
                <MenuItem value="CONTRACT_VALIDATION">Contract Validation</MenuItem>
                <MenuItem value="SEMANTIC_MAPPING">Semantic Mapping</MenuItem>
                <MenuItem value="CONTRACT_MIGRATION">Contract Migration</MenuItem>
                <MenuItem value="SCHEDULED_INGESTION">Scheduled Ingestion</MenuItem>
                <MenuItem value="RETENTION_POLICY_ENFORCEMENT">Retention Policy</MenuItem>
                <MenuItem value="SEARCH_INDEX_UPDATE">Search Index Update</MenuItem>
              </Select>
            </FormControl>

            {hasActiveFilters && (
              <Button size="small" onClick={handleClearFilters}>
                Clear Filters
              </Button>
            )}
          </Box>
        </Paper>

        {/* Jobs Table */}
        {!data || data.count === 0 ? (
          <NoDataEmptyState
            title="No jobs found"
            description={hasActiveFilters ? 'Try adjusting your filters.' : 'No jobs have been created yet.'}
          />
        ) : (
          <>
            <Paper>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Job ID</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Resource</TableCell>
                      <TableCell>Started</TableCell>
                      <TableCell>Completed</TableCell>
                      <TableCell>Created</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.results.map((job) => (
                      <TableRow
                        key={job.id}
                        sx={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/jobs/${job.id}`)}
                        hover
                      >
                        <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                          {job.id.substring(0, 8)}...
                        </TableCell>
                        <TableCell>
                          <Chip label={formatJobType(job.type)} size="small" variant="outlined" />
                        </TableCell>
                        <TableCell>
                          <Badge variant={getJobStatusBadgeVariant(job.status)} size="sm">
                            {job.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {job.resource_type}: {job.resource_id.substring(0, 8)}...
                          </Typography>
                        </TableCell>
                        <TableCell>{formatDate(job.started_at)}</TableCell>
                        <TableCell>{formatDate(job.completed_at)}</TableCell>
                        <TableCell>{formatDate(job.created_at)}</TableCell>
                        <TableCell align="right">
                          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                            {canCancelJob(job.status) && (
                              <Tooltip title="Cancel Job">
                                <IconButton
                                  size="small"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleCancelClick(job)
                                  }}
                                  color="error"
                                >
                                  <CancelIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            <Tooltip title="View Details">
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  navigate(`/jobs/${job.id}`)
                                }}
                              >
                                <ArrowForwardIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

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
                      setPage(1)
                    }}
                    totalItems={data.count}
                    pageSizeOptions={[10, 20, 50, 100]}
                  />
                </Box>
              )}
            </Paper>
          </>
        )}

        {/* Cancel Job Dialog */}
        <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)}>
          <DialogTitle>Cancel Job</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to cancel this job? This action cannot be undone.
            </DialogContentText>
            {jobToCancel && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Job ID: {jobToCancel.id}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Type: {formatJobType(jobToCancel.type)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Status: {jobToCancel.status}
                </Typography>
              </Box>
            )}
            {cancelJobMutation.isError && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {cancelJobMutation.error?.message || 'Failed to cancel job'}
              </Alert>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCancelDialogOpen(false)} disabled={cancelJobMutation.isPending}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirmCancel}
              color="error"
              variant="contained"
              disabled={cancelJobMutation.isPending}
            >
              {cancelJobMutation.isPending ? 'Cancelling...' : 'Cancel Job'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

JobsPage.displayName = 'JobsPage'

