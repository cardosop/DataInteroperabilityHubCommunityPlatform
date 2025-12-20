/**
 * Real-time Job Status Component
 *
 * Displays job status with real-time updates via WebSocket.
 * Automatically subscribes to job events and updates UI in real-time.
 */

import React, { useEffect, useState, useMemo } from 'react'
import { Box, Typography, LinearProgress, Chip, Tooltip } from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Cancel as CancelIcon,
  HourglassEmpty as HourglassIcon,
  PlayArrow as PlayIcon,
} from '@mui/icons-material'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useJob, useJobStatus } from '@/hooks/useJobs'
import { useQueryClient } from '@tanstack/react-query'
import type { Job, JobStatus } from '@/lib/api/jobs'
import type { EventMessage } from '@/lib/api/websocket'
import { Badge } from '@/components/data-display/Badge'
import { CircularProgress } from '@/components/feedback/CircularProgress'
import { spacing, colors } from '@/styles/tokens'

export interface RealtimeJobStatusProps {
  /**
   * Job ID to monitor
   */
  jobId: string
  /**
   * Show detailed information
   * @default true
   */
  showDetails?: boolean
  /**
   * Show progress indicator
   * @default true
   */
  showProgress?: boolean
  /**
   * Callback when job reaches terminal state
   */
  onComplete?: (job: Job) => void
  /**
   * Callback when job fails
   */
  onError?: (job: Job) => void
  /**
   * Custom className
   */
  className?: string
}

/**
 * Get status icon for job status
 */
const getStatusIcon = (status: JobStatus) => {
  switch (status) {
    case 'COMPLETED':
      return <CheckCircleIcon sx={{ color: colors.success[500], fontSize: 20 }} />
    case 'FAILED':
      return <ErrorIcon sx={{ color: colors.error[500], fontSize: 20 }} />
    case 'CANCELLED':
      return <CancelIcon sx={{ color: colors.gray[500], fontSize: 20 }} />
    case 'RUNNING':
      return <PlayIcon sx={{ color: colors.info[500], fontSize: 20 }} />
    case 'PENDING':
    default:
      return <HourglassIcon sx={{ color: colors.warning[500], fontSize: 20 }} />
  }
}

/**
 * Get status color for badge
 */
const getStatusColor = (status: JobStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' => {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'FAILED':
      return 'error'
    case 'CANCELLED':
      return 'neutral'
    case 'RUNNING':
      return 'info'
    case 'PENDING':
    default:
      return 'warning'
  }
}

/**
 * Format job type for display
 */
const formatJobType = (type: string): string => {
  return type
    .split('_')
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(' ')
}

/**
 * RealtimeJobStatus component
 */
export const RealtimeJobStatus: React.FC<RealtimeJobStatusProps> = ({
  jobId,
  showDetails = true,
  showProgress = true,
  onComplete,
  onError,
  className,
}) => {
  const [lastEvent, setLastEvent] = useState<EventMessage | null>(null)

  // Subscribe to job events via WebSocket
  const { isConnected } = useWebSocket(
    ['job.started', 'job.completed', 'job.failed', 'job.cancelled'],
    (event: EventMessage) => {
      if (event.data?.job_id === jobId) {
        setLastEvent(event)
      }
    }
  )

  // Get job data (fallback to polling if WebSocket not connected)
  const { data: job, isLoading, error } = useJob(jobId, {
    enabled: !!jobId,
  })

  // Poll job status if WebSocket is not connected
  const { data: polledJob } = useJobStatus(jobId, {
    enabled: !!jobId && !isConnected,
    interval: 2000,
    onTerminal: (job) => {
      if (job.status === 'COMPLETED') {
        onComplete?.(job)
      } else if (job.status === 'FAILED') {
        onError?.(job)
      }
    },
  })

  // Use WebSocket job if available, otherwise use polled job
  const currentJob = job || polledJob

  const queryClient = useQueryClient()

  // Update job when WebSocket event is received
  useEffect(() => {
    if (lastEvent && lastEvent.data?.job_id === jobId) {
      // Job status updated via WebSocket
      // Invalidate job query to trigger refetch
      queryClient.invalidateQueries({ queryKey: ['queries', 'jobs', 'detail', jobId] })
    }
  }, [lastEvent, jobId, queryClient])

  // Handle job completion
  useEffect(() => {
    if (currentJob) {
      if (currentJob.status === 'COMPLETED') {
        onComplete?.(currentJob)
      } else if (currentJob.status === 'FAILED') {
        onError?.(currentJob)
      }
    }
  }, [currentJob, onComplete, onError])

  if (isLoading) {
    return (
      <Box className={className}>
        <CircularProgress size="sm" />
        <Typography variant="body2" sx={{ marginTop: spacing[1] }}>
          Loading job status...
        </Typography>
      </Box>
    )
  }

  if (error || !currentJob) {
    return (
      <Box className={className}>
        <Badge variant="error">Job not found</Badge>
      </Box>
    )
  }

  const statusColor = getStatusColor(currentJob.status)
  const isRunning = currentJob.status === 'RUNNING'
  const isTerminal = ['COMPLETED', 'FAILED', 'CANCELLED'].includes(currentJob.status)

  return (
    <Box
      className={className}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: spacing[2],
        padding: spacing[2],
        border: `1px solid ${colors.semantic.borderDivider}`,
        borderRadius: 1,
        backgroundColor: 'background.paper',
      }}
    >
      {/* Status Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: spacing[2] }}>
        {getStatusIcon(currentJob.status)}
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: spacing[1] }}>
            <Badge variant={statusColor}>{currentJob.status}</Badge>
            <Chip label={formatJobType(currentJob.type)} size="small" variant="outlined" />
            {isConnected && (
              <Tooltip title="Real-time updates active">
                <Badge variant="info" size="sm">
                  Live
                </Badge>
              </Tooltip>
            )}
          </Box>
          {showDetails && (
            <Typography variant="caption" color="text.secondary" sx={{ marginTop: spacing[0.5] }}>
              Job ID: {currentJob.id}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Progress Indicator */}
      {showProgress && isRunning && (
        <Box>
          <LinearProgress
            sx={{
              height: 6,
              borderRadius: 1,
            }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ marginTop: spacing[0.5] }}>
            Job is running...
          </Typography>
        </Box>
      )}

      {/* Error Message */}
      {currentJob.status === 'FAILED' && currentJob.error_message && (
        <Box
          sx={{
            padding: spacing[2],
            backgroundColor: colors.error[50],
            borderRadius: 1,
            border: `1px solid ${colors.error[200]}`,
          }}
        >
          <Typography variant="body2" color="error">
            {currentJob.error_message}
          </Typography>
        </Box>
      )}

      {/* Timestamps */}
      {showDetails && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[0.5] }}>
          {currentJob.started_at && (
            <Typography variant="caption" color="text.secondary">
              Started: {new Date(currentJob.started_at).toLocaleString()}
            </Typography>
          )}
          {currentJob.completed_at && (
            <Typography variant="caption" color="text.secondary">
              Completed: {new Date(currentJob.completed_at).toLocaleString()}
            </Typography>
          )}
          {!isTerminal && (
            <Typography variant="caption" color="text.secondary">
              Last updated: {new Date(currentJob.updated_at).toLocaleString()}
            </Typography>
          )}
        </Box>
      )}

      {/* Result Summary */}
      {showDetails && currentJob.status === 'COMPLETED' && currentJob.result_json && (
        <Box
          sx={{
            padding: spacing[2],
            backgroundColor: colors.success[50],
            borderRadius: 1,
            border: `1px solid ${colors.success[200]}`,
          }}
        >
          <Typography variant="body2" color="success.main">
            Job completed successfully
          </Typography>
        </Box>
      )}
    </Box>
  )
}

RealtimeJobStatus.displayName = 'RealtimeJobStatus'

