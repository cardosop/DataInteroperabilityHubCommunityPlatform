/**
 * JobCard Component
 *
 * Card component for displaying job information in a card layout.
 * Shows job type, status, resource information, progress, and timestamps.
 */

import React, { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Tooltip,
  Alert,
} from '@mui/material'
import { formatDistanceToNow } from 'date-fns'
import type { Job } from '@/lib/api/jobs'
import { JobStatusIndicator } from '../JobStatusIndicator'
import { JobProgress } from '../JobProgress'

export interface JobCardProps {
  /**
   * Job data
   */
  job: Job
  /**
   * Clickable card (navigates to detail page)
   * @default true
   */
  clickable?: boolean
  /**
   * Callback when card is clicked
   */
  onClick?: (job: Job) => void
  /**
   * Show progress
   * @default true
   */
  showProgress?: boolean
  /**
   * Show error message
   * @default true
   */
  showErrorMessage?: boolean
  /**
   * Additional card props
   */
  cardProps?: React.ComponentProps<typeof Card>
}

/**
 * Format job type for display
 */
function formatJobType(type: string): string {
  return type
    .split('_')
    .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
    .join(' ')
}

/**
 * Format resource type for display
 */
function formatResourceType(type: string): string {
  return type.charAt(0) + type.slice(1).toLowerCase()
}

/**
 * Get progress from job details
 */
function getJobProgress(job: Job): { progress?: number; currentStep?: string } {
  if (!job.details_json) {
    return {}
  }

  const progress = job.details_json.progress
  const currentStep = job.details_json.current_step || job.details_json.step

  return {
    progress: typeof progress === 'number' ? progress : undefined,
    currentStep: typeof currentStep === 'string' ? currentStep : undefined,
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
 * JobCard Component
 *
 * @example
 * ```tsx
 * <JobCard
 *   job={job}
 *   onClick={(job) => navigate(`/jobs/${job.id}`)}
 * />
 * ```
 */
const JobCardComponent: React.FC<JobCardProps> = ({
  job,
  clickable = true,
  onClick,
  showProgress = true,
  showErrorMessage = true,
  cardProps,
}) => {
  const navigate = useNavigate()
  const { progress, currentStep } = getJobProgress(job)

  const handleClick = useCallback(() => {
    if (!clickable) return
    if (onClick) {
      onClick(job)
    } else {
      navigate(`/jobs/${job.id}`)
    }
  }, [clickable, onClick, job, navigate])

  return (
    <Card
      sx={{
        cursor: clickable ? 'pointer' : 'default',
        '&:hover': clickable ? { boxShadow: 3 } : {},
        transition: 'box-shadow 0.2s',
      }}
      onClick={handleClick}
      {...cardProps}
    >
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box>
            <Typography variant="h6" gutterBottom>
              {formatJobType(job.type)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatResourceType(job.resource_type)}: {job.resource_id}
            </Typography>
          </Box>
          <JobStatusIndicator status={job.status} />
        </Box>

        {/* Error Message */}
        {showErrorMessage && job.status === 'FAILED' && job.error_message && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {job.error_message}
          </Alert>
        )}

        {/* Progress */}
        {showProgress && (progress !== undefined || currentStep) && (
          <Box sx={{ mb: 2 }}>
            <JobProgress progress={progress} currentStep={currentStep} />
          </Box>
        )}

        {/* Metadata */}
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 2 }}>
          <Tooltip title={job.created_at}>
            <Typography variant="body2" color="text.secondary">
              Created: {formatDate(job.created_at)}
            </Typography>
          </Tooltip>
          {job.started_at && (
            <Tooltip title={job.started_at}>
              <Typography variant="body2" color="text.secondary">
                Started: {formatDate(job.started_at)}
              </Typography>
            </Tooltip>
          )}
          {job.completed_at && (
            <Tooltip title={job.completed_at}>
              <Typography variant="body2" color="text.secondary">
                Completed: {formatDate(job.completed_at)}
              </Typography>
            </Tooltip>
          )}
          {job.timeout_seconds && (
            <Typography variant="body2" color="text.secondary">
              Timeout: {Math.round(job.timeout_seconds / 60)} min
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  )
}

// Memoize JobCard to prevent unnecessary re-renders when parent re-renders
// Only re-render if job data or props change
export const JobCard = React.memo(JobCardComponent, (prevProps, nextProps) => {
  // Custom comparison: only re-render if job ID changes or other props change
  return (
    prevProps.job.id === nextProps.job.id &&
    prevProps.job.status === nextProps.job.status &&
    prevProps.job.type === nextProps.job.type &&
    prevProps.clickable === nextProps.clickable &&
    prevProps.showProgress === nextProps.showProgress &&
    prevProps.showErrorMessage === nextProps.showErrorMessage &&
    prevProps.onClick === nextProps.onClick
  )
})

