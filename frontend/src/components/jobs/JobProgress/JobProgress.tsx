/**
 * JobProgress Component
 *
 * Reusable component for displaying job progress with progress bar and current step.
 * Shows progress percentage and optional current step information.
 */

import React from 'react'
import { Box, Typography, LinearProgress } from '@mui/material'

export interface JobProgressProps {
  /**
   * Progress percentage (0-100)
   * If not provided, shows indeterminate progress
   */
  progress?: number
  /**
   * Current step description
   */
  currentStep?: string
  /**
   * Show percentage text
   * @default true
   */
  showPercentage?: boolean
  /**
   * Show current step
   * @default true
   */
  showCurrentStep?: boolean
  /**
   * Size variant
   * @default 'medium'
   */
  size?: 'small' | 'medium'
}

/**
 * JobProgress Component
 *
 * @example
 * ```tsx
 * <JobProgress progress={65} currentStep="Validating data" />
 * <JobProgress /> // Indeterminate progress
 * ```
 */
export const JobProgress: React.FC<JobProgressProps> = ({
  progress,
  currentStep,
  showPercentage = true,
  showCurrentStep = true,
  size = 'medium',
}) => {
  const height = size === 'small' ? 4 : 8

  return (
    <Box>
      {(showPercentage || showCurrentStep) && (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          {showPercentage && progress !== undefined && (
            <Typography variant="body2" color="text.secondary">
              {Math.round(progress)}%
            </Typography>
          )}
          {showCurrentStep && currentStep && (
            <Typography variant="body2" color="text.secondary">
              {currentStep}
            </Typography>
          )}
        </Box>
      )}
      <LinearProgress
        variant={progress !== undefined ? 'determinate' : 'indeterminate'}
        value={progress}
        sx={{ height, borderRadius: 1 }}
      />
    </Box>
  )
}

