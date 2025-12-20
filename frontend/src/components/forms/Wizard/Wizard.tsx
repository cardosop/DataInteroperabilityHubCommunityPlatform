/**
 * Wizard Component
 *
 * Multi-step form component for breaking complex forms into manageable steps.
 * Supports validation, progress tracking, and step navigation.
 */

import React, { useState, useCallback } from 'react'
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Button,
  Paper,
  Typography,
  CircularProgress,
} from '@mui/material'
import { spacing } from '@/styles/tokens'

export interface WizardStep {
  /**
   * Step label
   */
  label: string
  /**
   * Step description (optional)
   */
  description?: string
  /**
   * Step content component
   */
  content: React.ReactNode
  /**
   * Step validation function
   * Return true if step is valid, false otherwise
   */
  validate?: () => boolean | Promise<boolean>
  /**
   * Whether step can be skipped
   */
  skippable?: boolean
  /**
   * Whether step is optional
   */
  optional?: boolean
}

export interface WizardProps {
  /**
   * Wizard steps
   */
  steps: WizardStep[]
  /**
   * Callback when wizard is completed
   */
  onComplete?: (data: Record<string, unknown>) => void
  /**
   * Callback when wizard is cancelled
   */
  onCancel?: () => void
  /**
   * Initial step index
   */
  initialStep?: number
  /**
   * Show step numbers
   */
  showStepNumbers?: boolean
  /**
   * Allow navigation to previous steps
   */
  allowBackNavigation?: boolean
  /**
   * Show progress percentage
   */
  showProgress?: boolean
  /**
   * Loading state
   */
  loading?: boolean
}

/**
 * Wizard component for multi-step forms
 */
export const Wizard: React.FC<WizardProps> = ({
  steps,
  onComplete,
  onCancel,
  initialStep = 0,
  showStepNumbers = true,
  allowBackNavigation = true,
  showProgress = true,
  loading = false,
}) => {
  const [activeStep, setActiveStep] = useState(initialStep)
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set())
  const [validating, setValidating] = useState(false)

  const totalSteps = steps.length
  const progress = ((activeStep + 1) / totalSteps) * 100

  const isStepCompleted = (stepIndex: number): boolean => {
    return completedSteps.has(stepIndex)
  }

  const isStepOptional = (stepIndex: number): boolean => {
    return steps[stepIndex]?.optional ?? false
  }

  const canProceed = (stepIndex: number): boolean => {
    if (allowBackNavigation) return true
    // Can only proceed if all previous steps are completed
    for (let i = 0; i < stepIndex; i++) {
      if (!isStepCompleted(i) && !isStepOptional(i)) {
        return false
      }
    }
    return true
  }

  const handleNext = useCallback(async () => {
    const currentStep = steps[activeStep]

    // Validate current step if validation function exists
    if (currentStep?.validate) {
      setValidating(true)
      try {
        const isValid = await currentStep.validate()
        if (!isValid) {
          setValidating(false)
          return
        }
      } catch (error) {
        console.error('Step validation error:', error)
        setValidating(false)
        return
      }
      setValidating(false)
    }

    // Mark step as completed
    setCompletedSteps((prev) => new Set([...prev, activeStep]))

    // Move to next step or complete
    if (activeStep === totalSteps - 1) {
      // Last step - complete wizard
      onComplete?.({})
    } else {
      setActiveStep((prev) => prev + 1)
    }
  }, [activeStep, steps, totalSteps, onComplete])

  const handleBack = useCallback(() => {
    if (activeStep > 0) {
      setActiveStep((prev) => prev - 1)
    }
  }, [activeStep])

  const handleStepClick = useCallback(
    (stepIndex: number) => {
      if (allowBackNavigation && canProceed(stepIndex)) {
        setActiveStep(stepIndex)
      }
    },
    [allowBackNavigation, canProceed]
  )

  const handleSkip = useCallback(() => {
    if (steps[activeStep]?.skippable) {
      if (activeStep === totalSteps - 1) {
        onComplete?.({})
      } else {
        setActiveStep((prev) => prev + 1)
      }
    }
  }, [activeStep, steps, totalSteps, onComplete])

  const currentStep = steps[activeStep]
  const isLastStep = activeStep === totalSteps - 1
  const canGoBack = activeStep > 0 && allowBackNavigation

  return (
    <Box sx={{ width: '100%' }}>
      {/* Progress indicator */}
      {showProgress && (
        <Box sx={{ marginBottom: spacing[4] }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Step {activeStep + 1} of {totalSteps} ({Math.round(progress)}%)
          </Typography>
          <Box
            sx={{
              width: '100%',
              height: 4,
              backgroundColor: 'action.disabledBackground',
              borderRadius: 2,
              overflow: 'hidden',
            }}
          >
            <Box
              sx={{
                width: `${progress}%`,
                height: '100%',
                backgroundColor: 'primary.main',
                transition: 'width 0.3s ease',
              }}
            />
          </Box>
        </Box>
      )}

      {/* Stepper */}
      <Stepper activeStep={activeStep} sx={{ marginBottom: spacing[6] }}>
        {steps.map((step, index) => (
          <Step
            key={index}
            completed={isStepCompleted(index)}
            sx={{
              cursor: allowBackNavigation && canProceed(index) ? 'pointer' : 'default',
            }}
            onClick={() => handleStepClick(index)}
          >
            <StepLabel
              optional={
                step.optional ? (
                  <Typography variant="caption">Optional</Typography>
                ) : undefined
              }
            >
              {step.label}
            </StepLabel>
          </Step>
        ))}
      </Stepper>

      {/* Step content */}
      <Paper
        sx={{
          padding: spacing[4],
          marginBottom: spacing[4],
          minHeight: '400px',
        }}
      >
        {currentStep?.description && (
          <Typography variant="h6" gutterBottom>
            {currentStep.description}
          </Typography>
        )}
        {loading ? (
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              minHeight: '300px',
            }}
          >
            <CircularProgress />
          </Box>
        ) : (
          currentStep?.content
        )}
      </Paper>

      {/* Navigation buttons */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingTop: spacing[4],
          borderTop: 1,
          borderColor: 'divider',
        }}
      >
        <Box>
          {canGoBack && (
            <Button onClick={handleBack} disabled={validating || loading}>
              Back
            </Button>
          )}
          {onCancel && (
            <Button onClick={onCancel} sx={{ marginLeft: spacing[2] }}>
              Cancel
            </Button>
          )}
        </Box>

        <Box>
          {currentStep?.skippable && !isLastStep && (
            <Button
              onClick={handleSkip}
              disabled={validating || loading}
              sx={{ marginRight: spacing[2] }}
            >
              Skip
            </Button>
          )}
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={validating || loading}
          >
            {validating ? (
              <>
                <CircularProgress size={16} sx={{ marginRight: 1 }} />
                Validating...
              </>
            ) : isLastStep ? (
              'Complete'
            ) : (
              'Next'
            )}
          </Button>
        </Box>
      </Box>
    </Box>
  )
}

