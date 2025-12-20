/**
 * JobStatusIndicator Component
 *
 * Reusable component for displaying job status with color-coded badges and icons.
 * Shows job status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED) with appropriate styling.
 */

import React from 'react'
import { Chip } from '@mui/material'
import {
  Schedule as ScheduleIcon,
  PlayArrow as PlayArrowIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material'
import type { JobStatus } from '@/lib/api/jobs'

export interface JobStatusIndicatorProps {
  /**
   * Job status
   */
  status: JobStatus
  /**
   * Size of the indicator
   * @default 'medium'
   */
  size?: 'small' | 'medium'
  /**
   * Show icon
   * @default true
   */
  showIcon?: boolean
  /**
   * Custom label (overrides default status label)
   */
  label?: string
}

/**
 * Get status color
 */
function getStatusColor(status: JobStatus): 'default' | 'primary' | 'success' | 'error' | 'warning' {
  switch (status) {
    case 'PENDING':
      return 'default'
    case 'RUNNING':
      return 'primary'
    case 'COMPLETED':
      return 'success'
    case 'FAILED':
      return 'error'
    case 'CANCELLED':
      return 'warning'
    default:
      return 'default'
  }
}

/**
 * Get status icon
 */
function getStatusIcon(status: JobStatus) {
  switch (status) {
    case 'PENDING':
      return <ScheduleIcon fontSize="small" />
    case 'RUNNING':
      return <PlayArrowIcon fontSize="small" />
    case 'COMPLETED':
      return <CheckCircleIcon fontSize="small" />
    case 'FAILED':
      return <ErrorIcon fontSize="small" />
    case 'CANCELLED':
      return <CancelIcon fontSize="small" />
    default:
      return null
  }
}

/**
 * Get status label
 */
function getStatusLabel(status: JobStatus): string {
  switch (status) {
    case 'PENDING':
      return 'Pending'
    case 'RUNNING':
      return 'Running'
    case 'COMPLETED':
      return 'Completed'
    case 'FAILED':
      return 'Failed'
    case 'CANCELLED':
      return 'Cancelled'
    default:
      return status
  }
}

/**
 * JobStatusIndicator Component
 *
 * @example
 * ```tsx
 * <JobStatusIndicator status="RUNNING" />
 * <JobStatusIndicator status="COMPLETED" size="small" />
 * ```
 */
export const JobStatusIndicator: React.FC<JobStatusIndicatorProps> = ({
  status,
  size = 'medium',
  showIcon = true,
  label,
}) => {
  const displayLabel = label || getStatusLabel(status)
  const icon = showIcon ? getStatusIcon(status) : undefined

  return (
    <Chip
      label={displayLabel}
      icon={icon}
      color={getStatusColor(status)}
      size={size}
    />
  )
}

