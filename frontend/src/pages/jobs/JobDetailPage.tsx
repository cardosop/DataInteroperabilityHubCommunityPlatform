/**
 * Job Detail Page
 *
 * Comprehensive job detail page with:
 * - Job information and metadata
 * - Real-time job progress with automatic polling
 * - Job logs display
 * - Job errors display
 */

import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Paper,
  Chip,
  Button,
  IconButton,
  Divider,
  Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  LinearProgress,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  Cancel as CancelIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Assignment as AssignmentIcon,
  Description as DescriptionIcon,
  BugReport as BugReportIcon,
  Timeline as TimelineIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import { useJob, useJobStatus } from '@/hooks/useJobs'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { Job, JobType, JobStatus } from '@/lib/api/jobs'
import { canCancelJob, isJobTerminal, isJobRunning } from '@/lib/api/jobs'
import { queryKeys } from '@/lib/api/react-query'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import { JSONViewer } from '@/components/data-display/JSONViewer'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { useWebSocket } from '@/hooks/useWebSocket'
import type { WebSocketEvent } from '@/lib/api/websocket-events'

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
 * Format job type for display
 */
function formatJobType(type: JobType): string {
  return type
    .split('_')
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(' ')
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return format(new Date(dateString), 'PPpp')
  } catch {
    return dateString
  }
}

/**
 * Format relative date for display
 */
function formatRelativeDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

/**
 * Calculate job duration
 */
function calculateDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return '—'
  const start = new Date(startedAt)
  const end = completedAt ? new Date(completedAt) : new Date()
  const diffMs = end.getTime() - start.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)

  if (diffHours > 0) {
    return `${diffHours}h ${diffMinutes % 60}m ${diffSeconds % 60}s`
  }
  if (diffMinutes > 0) {
    return `${diffMinutes}m ${diffSeconds % 60}s`
  }
  return `${diffSeconds}s`
}

/**
 * Extract logs from job details
 */
function extractLogs(job: Job): string[] {
  const logs: string[] = []

  // Extract from details_json
  if (job.details_json) {
    if (job.details_json.logs && Array.isArray(job.details_json.logs)) {
      logs.push(...job.details_json.logs.map((log: any) => String(log)))
    }
    if (job.details_json.log && typeof job.details_json.log === 'string') {
      logs.push(job.details_json.log)
    }
    if (job.details_json.output && typeof job.details_json.output === 'string') {
      logs.push(job.details_json.output)
    }
  }

  // Extract from result_json
  if (job.result_json) {
    if (job.result_json.logs && Array.isArray(job.result_json.logs)) {
      logs.push(...job.result_json.logs.map((log: any) => String(log)))
    }
    if (job.result_json.log && typeof job.result_json.log === 'string') {
      logs.push(job.result_json.log)
    }
    if (job.result_json.output && typeof job.result_json.output === 'string') {
      logs.push(job.result_json.output)
    }
  }

  return logs
}

/**
 * Extract progress information from job details
 */
function extractProgress(job: Job): { current?: number; total?: number; percentage?: number; message?: string } {
  if (job.details_json) {
    const progress = job.details_json.progress
    if (progress) {
      return {
        current: progress.current,
        total: progress.total,
        percentage: progress.percentage,
        message: progress.message,
      }
    }
  }

  if (job.result_json) {
    const progress = job.result_json.progress
    if (progress) {
      return {
        current: progress.current,
        total: progress.total,
        percentage: progress.percentage,
        message: progress.message,
      }
    }
  }

  return {}
}

/**
 * Job Detail Page Component
 */
export const JobDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast } = useToastManager()
  const queryClient = useQueryClient()

  // Cancel dialog state
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)

  // Track processed job events to avoid duplicate notifications
  const processedEventsRef = useRef<Set<string>>(new Set())

  // Fetch job data (initial load)
  const {
    data: job,
    isLoading: isLoadingJob,
    error: jobError,
    refetch: refetchJob,
  } = useJob(id!)

  // Handle WebSocket events for real-time job updates
  const handleJobEvent = useCallback(
    (event: WebSocketEvent) => {
      // Only process job events for this specific job
      if (!event.event_type.startsWith('job.') || event.data?.job_id !== id) {
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

      // Invalidate job query to trigger refetch with latest data
      queryClient.invalidateQueries({
        queryKey: queryKeys.jobs.detail(id!),
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
    [id, queryClient, showToast]
  )

  // Subscribe to job events via WebSocket for this specific job
  const { isConnected: isWebSocketConnected } = useWebSocket(
    ['job.started', 'job.completed', 'job.failed', 'job.cancelled'],
    handleJobEvent
  )

  // Use real-time status polling for running jobs (fallback if WebSocket not connected)
  const shouldPoll = job && !isJobTerminal(job.status) && !isWebSocketConnected
  const {
    data: polledJob,
    isLoading: isLoadingStatus,
  } = useJobStatus(id!, {
    enabled: shouldPoll,
    interval: 2000, // Poll every 2 seconds
    onStatusChange: (status, previousStatus) => {
      if (status === 'COMPLETED') {
        showToast({
          message: 'Job completed successfully',
          severity: 'success',
        })
      } else if (status === 'FAILED') {
        showToast({
          message: 'Job failed',
          severity: 'error',
        })
      }
    },
  })

  // Use polled job if available, otherwise use regular job
  const currentJob = polledJob || job

  // Cancel job mutation
  const cancelJobMutation = useMutation({
    mutationFn: async (jobId: string) => {
      const response = await apiClient.post<Job>(`/api/v1/jobs/jobs/${jobId}/cancel/`)
      return response.data
    },
    onSuccess: (data) => {
      // Invalidate jobs queries
      queryClient.invalidateQueries({
        queryKey: queryKeys.jobs.lists(),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.jobs.detail(data.id),
      })

      showToast({
        message: 'Job cancelled successfully',
        severity: 'success',
      })

      setCancelDialogOpen(false)
      refetchJob()
    },
    onError: (error: Error) => {
      showToast({
        message: error.message || 'Failed to cancel job',
        severity: 'error',
      })
    },
  })

  // Extract logs and progress
  const logs = useMemo(() => {
    if (!currentJob) return []
    return extractLogs(currentJob)
  }, [currentJob])

  const progress = useMemo(() => {
    if (!currentJob) return {}
    return extractProgress(currentJob)
  }, [currentJob])

  // Calculate duration
  const duration = useMemo(() => {
    if (!currentJob) return '—'
    return calculateDuration(currentJob.started_at, currentJob.completed_at)
  }, [currentJob])

  // Handle cancel job
  const handleCancelClick = useCallback(() => {
    setCancelDialogOpen(true)
  }, [])

  // Handle confirm cancel
  const handleConfirmCancel = useCallback(() => {
    if (currentJob) {
      cancelJobMutation.mutate(currentJob.id)
    }
  }, [currentJob, cancelJobMutation])

  // Loading state
  if (isLoadingJob) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading job details..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (jobError || !currentJob) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load job"
            message={jobError?.message || 'Job not found.'}
            onRetry={() => refetchJob()}
          />
        </Box>
      </Container>
    )
  }

  const isRunning = isJobRunning(currentJob.status)
  const isTerminal = isJobTerminal(currentJob.status)
  const canCancel = canCancelJob(currentJob.status)

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton onClick={() => navigate('/jobs')} size="small">
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h4" gutterBottom>
              Job Details
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Job ID: {currentJob.id}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {canCancel && (
              <Button
                variant="outlined"
                color="error"
                startIcon={<CancelIcon />}
                onClick={handleCancelClick}
                disabled={cancelJobMutation.isPending}
              >
                Cancel Job
              </Button>
            )}
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetchJob()} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Running Status Alert */}
        {isRunning && (
          <Alert severity="info" sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {isLoadingStatus && !isWebSocketConnected && <CircularProgress size={20} />}
              <Box sx={{ flex: 1 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Job is running
                </Typography>
                <Typography variant="body2">
                  {isWebSocketConnected
                    ? 'Real-time updates are active. This page will automatically update as the job progresses.'
                    : 'This page will automatically update as the job progresses (polling mode).'}
                </Typography>
              </Box>
              {isWebSocketConnected && (
                <Chip
                  label="Real-time"
                  size="small"
                  color="success"
                  sx={{ height: 24, fontSize: '0.7rem' }}
                />
              )}
            </Box>
          </Alert>
        )}

        {/* Job Information */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <InfoIcon />
            <Typography variant="h6">Job Information</Typography>
          </Box>
          <Divider sx={{ my: 2 }} />

          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Status
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Badge variant={getJobStatusBadgeVariant(currentJob.status)} size="sm">
                    {currentJob.status}
                  </Badge>
                  {isRunning && <CircularProgress size={16} />}
                </Box>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Type
                </Typography>
                <Chip label={formatJobType(currentJob.type)} size="small" />
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Resource
                </Typography>
                <Typography variant="body1">
                  {currentJob.resource_type}: {currentJob.resource_id}
                </Typography>
              </Box>

              {currentJob.timeout_seconds && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Timeout
                  </Typography>
                  <Typography variant="body1">{currentJob.timeout_seconds} seconds</Typography>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} md={6}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Created
                </Typography>
                <Typography variant="body1">
                  {formatDate(currentJob.created_at)}
                  <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                    ({formatRelativeDate(currentJob.created_at)})
                  </Typography>
                </Typography>
              </Box>

              {currentJob.started_at && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Started
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(currentJob.started_at)}
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatRelativeDate(currentJob.started_at)})
                    </Typography>
                  </Typography>
                </Box>
              )}

              {currentJob.completed_at && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Completed
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(currentJob.completed_at)}
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatRelativeDate(currentJob.completed_at)})
                    </Typography>
                  </Typography>
                </Box>
              )}

              {(currentJob.started_at || currentJob.completed_at) && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Duration
                  </Typography>
                  <Typography variant="body1">{duration}</Typography>
                </Box>
              )}
            </Grid>
          </Grid>
        </Paper>

        {/* Job Progress */}
        {isRunning && (progress.percentage !== undefined || progress.current !== undefined) && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <TimelineIcon />
              <Typography variant="h6">Job Progress</Typography>
            </Box>
            <Divider sx={{ my: 2 }} />

            <Box>
              {progress.percentage !== undefined ? (
                <>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                    <LinearProgress
                      variant="determinate"
                      value={progress.percentage}
                      sx={{ flex: 1, height: 8, borderRadius: 4 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      {progress.percentage.toFixed(0)}%
                    </Typography>
                  </Box>
                  {progress.message && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      {progress.message}
                    </Typography>
                  )}
                </>
              ) : progress.current !== undefined && progress.total !== undefined ? (
                <>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
                    <LinearProgress
                      variant="determinate"
                      value={(progress.current / progress.total) * 100}
                      sx={{ flex: 1, height: 8, borderRadius: 4 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      {progress.current} / {progress.total}
                    </Typography>
                  </Box>
                  {progress.message && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      {progress.message}
                    </Typography>
                  )}
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  Progress information not available
                </Typography>
              )}
            </Box>
          </Paper>
        )}

        {/* Job Errors */}
        {currentJob.error_message && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <ErrorIcon color="error" />
              <Typography variant="h6">Error</Typography>
            </Box>
            <Divider sx={{ my: 2 }} />
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="body1" sx={{ fontWeight: 600, mb: 1 }}>
                Error Message
              </Typography>
              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                {currentJob.error_message}
              </Typography>
            </Alert>

            {currentJob.result_json?.error && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                  Error Details
                </Typography>
                <JSONViewer data={currentJob.result_json.error} />
              </Box>
            )}
          </Paper>
        )}

        {/* Job Logs */}
        {logs.length > 0 && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <DescriptionIcon />
              <Typography variant="h6">Job Logs</Typography>
              <Chip label={`${logs.length} log entries`} size="small" />
            </Box>
            <Divider sx={{ my: 2 }} />
            <Box
              sx={{
                backgroundColor: '#1e1e1e',
                color: '#d4d4d4',
                p: 2,
                borderRadius: 1,
                maxHeight: 400,
                overflow: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
              }}
            >
              {logs.map((log, index) => (
                <Box key={index} sx={{ mb: 0.5 }}>
                  <Typography
                    component="pre"
                    sx={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'inherit',
                      fontSize: 'inherit',
                    }}
                  >
                    {log}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        )}

        {/* Job Details JSON */}
        {(currentJob.details_json || currentJob.result_json) && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <AssignmentIcon />
                  <Typography variant="h6">Raw Job Data</Typography>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {currentJob.details_json && (
                    <Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                        Details JSON
                      </Typography>
                      <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                        <JSONViewer data={currentJob.details_json} />
                      </Box>
                    </Box>
                  )}
                  {currentJob.result_json && (
                    <Box>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                        Result JSON
                      </Typography>
                      <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                        <JSONViewer data={currentJob.result_json} />
                      </Box>
                    </Box>
                  )}
                </Box>
              </AccordionDetails>
            </Accordion>
          </Paper>
        )}

        {/* Cancel Job Dialog */}
        <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)}>
          <DialogTitle>Cancel Job</DialogTitle>
          <DialogContent>
            <DialogContentText>
              Are you sure you want to cancel this job? This action cannot be undone.
            </DialogContentText>
            {currentJob && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Job ID: {currentJob.id}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Type: {formatJobType(currentJob.type)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Status: {currentJob.status}
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

JobDetailPage.displayName = 'JobDetailPage'

