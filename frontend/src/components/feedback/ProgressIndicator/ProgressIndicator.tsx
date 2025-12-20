/**
 * ProgressIndicator Component
 *
 * Comprehensive progress indicator supporting linear, circular, and step-based progress.
 */

import React from 'react'
import {
  Box,
  LinearProgress,
  CircularProgress,
  Stepper,
  Step,
  StepLabel,
  Typography,
} from '@mui/material'
import { spacing } from '@/styles/tokens'
import { ProgressBar } from '../ProgressBar'

export interface ProgressIndicatorProps {
  /**
   * Type of progress indicator
   */
  variant: 'linear' | 'circular' | 'step'
  /**
   * Progress value (0-100) for linear/circular
   */
  value?: number
  /**
   * Current step index (for step variant)
   */
  currentStep?: number
  /**
   * Total number of steps (for step variant)
   */
  totalSteps?: number
  /**
   * Step labels (for step variant)
   */
  steps?: string[]
  /**
   * Label text
   */
  label?: string
  /**
   * Show percentage
   */
  showPercentage?: boolean
  /**
   * Size of circular progress
   */
  size?: number
  /**
   * Estimated time remaining (optional)
   */
  estimatedTime?: string
  /**
   * Show cancel button
   */
  showCancel?: boolean
  /**
   * Cancel callback
   */
  onCancel?: () => void
  /**
   * Indeterminate progress
   */
  indeterminate?: boolean
}

/**
 * ProgressIndicator component
 */
export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({
  variant,
  value = 0,
  currentStep,
  totalSteps,
  steps,
  label,
  showPercentage = false,
  size = 40,
  estimatedTime,
  showCancel = false,
  onCancel,
  indeterminate = false,
}) => {
  if (variant === 'step') {
    const stepLabels = steps || []
    const current = currentStep ?? 0
    const total = totalSteps ?? stepLabels.length

    return (
      <Box sx={{ width: '100%' }}>
        {label && (
          <Typography variant="body2" sx={{ marginBottom: spacing[2] }}>
            {label}
          </Typography>
        )}
        <Stepper activeStep={current} sx={{ marginBottom: spacing[2] }}>
          {stepLabels.map((stepLabel, index) => (
            <Step key={index} completed={index < current}>
              <StepLabel>{stepLabel}</StepLabel>
            </Step>
          ))}
        </Stepper>
        {total > 0 && (
          <Typography variant="caption" color="text.secondary">
            Step {current + 1} of {total}
          </Typography>
        )}
      </Box>
    )
  }

  if (variant === 'circular') {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: spacing[2],
        }}
      >
        {label && <Typography variant="body2">{label}</Typography>}
        <Box sx={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress
            variant={indeterminate ? 'indeterminate' : 'determinate'}
            value={indeterminate ? undefined : value}
            size={size}
          />
          {!indeterminate && showPercentage && (
            <Box
              sx={{
                top: 0,
                left: 0,
                bottom: 0,
                right: 0,
                position: 'absolute',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="caption" component="div" color="text.secondary">
                {Math.round(value)}%
              </Typography>
            </Box>
          )}
        </Box>
        {estimatedTime && (
          <Typography variant="caption" color="text.secondary">
            {estimatedTime}
          </Typography>
        )}
        {showCancel && onCancel && (
          <button
            onClick={onCancel}
            style={{
              marginTop: spacing[1],
              padding: `${spacing[1]}px ${spacing[2]}px`,
              border: '1px solid',
              borderRadius: '4px',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        )}
      </Box>
    )
  }

  // Linear variant
  return (
    <Box sx={{ width: '100%' }}>
      {label && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: spacing[1],
          }}
        >
          <Typography variant="body2">{label}</Typography>
          {showPercentage && !indeterminate && (
            <Typography variant="body2" color="text.secondary">
              {Math.round(value)}%
            </Typography>
          )}
        </Box>
      )}
      <ProgressBar
        value={value}
        variant={indeterminate ? 'indeterminate' : 'determinate'}
        showValue={showPercentage}
      />
      {estimatedTime && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ marginTop: spacing[1], display: 'block' }}
        >
          Estimated time: {estimatedTime}
        </Typography>
      )}
      {showCancel && onCancel && (
        <Box sx={{ marginTop: spacing[2], textAlign: 'right' }}>
          <button
            onClick={onCancel}
            style={{
              padding: `${spacing[1]}px ${spacing[2]}px`,
              border: '1px solid',
              borderRadius: '4px',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </Box>
      )}
    </Box>
  )
}

