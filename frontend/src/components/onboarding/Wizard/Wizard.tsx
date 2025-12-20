/**
 * Multi-step Onboarding Wizard Component
 *
 * Comprehensive wizard component for multi-step onboarding flows.
 * Features:
 * - Step navigation (next, back, cancel, skip)
 * - Progress indicator (step progress, percentage)
 * - Step validation (validate before proceeding)
 * - Step persistence (save progress, resume later)
 * - Wizard state management (current step, completed steps, form data)
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Box,
  Button,
  Paper,
  Typography,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  ArrowForward as ArrowForwardIcon,
  Close as CloseIcon,
  Save as SaveIcon,
} from '@mui/icons-material'
import { Stepper } from '@/components/navigation/Stepper'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { spacing, colors } from '@/styles/tokens'

/**
 * Wizard step definition
 */
export interface WizardStep {
  /**
   * Step ID (unique identifier)
   */
  id: string
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
   * Receives wizard state and update functions as props
   */
  content: React.ComponentType<WizardStepContentProps>
  /**
   * Step validation function
   * Receives current form data and returns validation result
   * @param formData - Current form data
   * @returns Validation result (true if valid, error message if invalid)
   */
  validate?: (formData: Record<string, any>) => boolean | string | Promise<boolean | string>
  /**
   * Whether step can be skipped
   */
  skippable?: boolean
  /**
   * Whether step is optional
   */
  optional?: boolean
  /**
   * Step-specific data transformation before saving
   */
  transformData?: (formData: Record<string, any>) => Record<string, any>
}

/**
 * Props passed to step content components
 */
export interface WizardStepContentProps {
  /**
   * Current form data (all steps combined)
   */
  formData: Record<string, any>
  /**
   * Update form data for a specific step
   */
  updateFormData: (stepId: string, data: Record<string, any>) => void
  /**
   * Current step index
   */
  stepIndex: number
  /**
   * Total number of steps
   */
  totalSteps: number
  /**
   * Whether step is valid
   */
  isValid: boolean
  /**
   * Validation error message
   */
  validationError?: string
}

/**
 * Wizard state (for persistence)
 */
export interface WizardState {
  /**
   * Current step index
   */
  currentStep: number
  /**
   * Completed step indices
   */
  completedSteps: number[]
  /**
   * Form data by step ID
   */
  formData: Record<string, Record<string, any>>
  /**
   * Timestamp when wizard was last saved
   */
  lastSaved?: string
  /**
   * Wizard ID (for identifying different wizard instances)
   */
  wizardId?: string
}

/**
 * Wizard component props
 */
export interface WizardProps {
  /**
   * Wizard steps
   */
  steps: WizardStep[]
  /**
   * Callback when wizard is completed
   * Receives all form data from all steps
   */
  onComplete?: (formData: Record<string, any>) => void | Promise<void>
  /**
   * Callback when wizard is cancelled
   */
  onCancel?: () => void
  /**
   * Initial step index
   * @default 0
   */
  initialStep?: number
  /**
   * Wizard ID for persistence (if not provided, persistence is disabled)
   */
  wizardId?: string
  /**
   * Enable step persistence
   * @default true
   */
  enablePersistence?: boolean
  /**
   * Show step numbers
   * @default true
   */
  showStepNumbers?: boolean
  /**
   * Allow navigation to previous steps
   * @default true
   */
  allowBackNavigation?: boolean
  /**
   * Show progress percentage
   * @default true
   */
  showProgress?: boolean
  /**
   * Show progress bar
   * @default true
   */
  showProgressBar?: boolean
  /**
   * Loading state
   */
  loading?: boolean
  /**
   * Auto-save interval in milliseconds (0 to disable)
   * @default 5000 (5 seconds)
   */
  autoSaveInterval?: number
  /**
   * Show confirmation dialog on cancel
   * @default true
   */
  confirmCancel?: boolean
  /**
   * Custom className
   */
  className?: string
}

/**
 * Multi-step onboarding wizard component
 */
export const Wizard: React.FC<WizardProps> = ({
  steps,
  onComplete,
  onCancel,
  initialStep = 0,
  wizardId,
  enablePersistence = true,
  showStepNumbers = true,
  allowBackNavigation = true,
  showProgress = true,
  showProgressBar = true,
  loading = false,
  autoSaveInterval = 5000,
  confirmCancel = true,
  className,
}) => {
  // Generate unique wizard ID if not provided
  const finalWizardId = useMemo(
    () => wizardId || (enablePersistence ? `wizard-${Date.now()}` : undefined),
    [wizardId, enablePersistence]
  )

  // Persistence key
  const persistenceKey = useMemo(
    () => (finalWizardId ? `wizard-state-${finalWizardId}` : null),
    [finalWizardId]
  )

  // Load saved state from localStorage
  const [savedState, setSavedState, clearSavedState] = useLocalStorage<WizardState | null>(
    persistenceKey || 'wizard-state-temp',
    null
  )

  // Wizard state
  const [currentStep, setCurrentStep] = useState<number>(() => {
    // Try to resume from saved state
    if (savedState && enablePersistence) {
      return savedState.currentStep
    }
    return initialStep
  })

  const [completedSteps, setCompletedSteps] = useState<Set<number>>(() => {
    if (savedState && enablePersistence) {
      return new Set(savedState.completedSteps)
    }
    return new Set<number>()
  })

  const [formData, setFormData] = useState<Record<string, Record<string, any>>>(() => {
    if (savedState && enablePersistence) {
      return savedState.formData || {}
    }
    return {}
  })

  const [validating, setValidating] = useState(false)
  const [validationError, setValidationError] = useState<string | undefined>()
  const [showCancelDialog, setShowCancelDialog] = useState(false)
  const [isCompleting, setIsCompleting] = useState(false)

  const totalSteps = steps.length
  const currentStepData = steps[currentStep]
  const isLastStep = currentStep === totalSteps - 1
  const canGoBack = currentStep > 0 && allowBackNavigation

  // Calculate progress
  const progress = useMemo(() => {
    const completedCount = completedSteps.size
    return Math.round(((completedCount + (currentStep === totalSteps - 1 ? 1 : 0)) / totalSteps) * 100)
  }, [completedSteps.size, currentStep, totalSteps])

  // Get current step's form data
  const currentStepFormData = useMemo(() => {
    return formData[currentStepData?.id] || {}
  }, [formData, currentStepData])

  // Get all form data combined
  const allFormData = useMemo(() => {
    return steps.reduce((acc, step) => {
      return { ...acc, ...(formData[step.id] || {}) }
    }, {})
  }, [formData, steps])

  // Save wizard state to localStorage
  const saveState = useCallback(() => {
    if (!enablePersistence || !persistenceKey) return

    const state: WizardState = {
      currentStep,
      completedSteps: Array.from(completedSteps),
      formData,
      lastSaved: new Date().toISOString(),
      wizardId: finalWizardId,
    }

    setSavedState(state)
  }, [enablePersistence, persistenceKey, currentStep, completedSteps, formData, finalWizardId, setSavedState])

  // Auto-save state
  useEffect(() => {
    if (!enablePersistence || autoSaveInterval === 0) return

    const interval = setInterval(() => {
      saveState()
    }, autoSaveInterval)

    return () => clearInterval(interval)
  }, [enablePersistence, autoSaveInterval, saveState])

  // Save state when form data changes
  useEffect(() => {
    if (enablePersistence) {
      saveState()
    }
  }, [formData, enablePersistence, saveState])

  // Update form data for a specific step
  const updateFormData = useCallback(
    (stepId: string, data: Record<string, any>) => {
      setFormData((prev) => ({
        ...prev,
        [stepId]: { ...prev[stepId], ...data },
      }))
    },
    []
  )

  // Validate current step
  const validateStep = useCallback(async (): Promise<boolean> => {
    if (!currentStepData?.validate) {
      return true
    }

    setValidating(true)
    setValidationError(undefined)

    try {
      const result = await currentStepData.validate(allFormData)

      if (result === true) {
        setValidating(false)
        return true
      } else if (typeof result === 'string') {
        setValidationError(result)
        setValidating(false)
        return false
      } else {
        setValidationError('Validation failed')
        setValidating(false)
        return false
      }
    } catch (error) {
      setValidationError(error instanceof Error ? error.message : 'Validation error occurred')
      setValidating(false)
      return false
    }
  }, [currentStepData, allFormData])

  // Handle next step
  const handleNext = useCallback(async () => {
    // Validate current step
    const isValid = await validateStep()
    if (!isValid) {
      return
    }

    // Mark step as completed
    setCompletedSteps((prev) => new Set([...prev, currentStep]))

    // Transform and save step data if transform function exists
    if (currentStepData?.transformData) {
      const transformedData = currentStepData.transformData(currentStepFormData)
      updateFormData(currentStepData.id, transformedData)
    }

    // Move to next step or complete
    if (isLastStep) {
      // Last step - complete wizard
      setIsCompleting(true)
      try {
        await onComplete?.(allFormData)
        // Clear saved state on successful completion
        if (enablePersistence && persistenceKey) {
          clearSavedState()
        }
      } catch (error) {
        console.error('Wizard completion error:', error)
        setIsCompleting(false)
      }
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }, [
    validateStep,
    currentStep,
    isLastStep,
    currentStepData,
    currentStepFormData,
    updateFormData,
    onComplete,
    allFormData,
    enablePersistence,
    persistenceKey,
    clearSavedState,
  ])

  // Handle back step
  const handleBack = useCallback(() => {
    if (canGoBack) {
      setCurrentStep((prev) => prev - 1)
      setValidationError(undefined)
    }
  }, [canGoBack])

  // Handle skip step
  const handleSkip = useCallback(() => {
    if (currentStepData?.skippable) {
      if (isLastStep) {
        setIsCompleting(true)
        onComplete?.(allFormData).finally(() => {
          setIsCompleting(false)
          if (enablePersistence && persistenceKey) {
            clearSavedState()
          }
        })
      } else {
        setCurrentStep((prev) => prev + 1)
      }
    }
  }, [currentStepData, isLastStep, onComplete, allFormData, enablePersistence, persistenceKey, clearSavedState])

  // Handle cancel
  const handleCancel = useCallback(() => {
    if (confirmCancel) {
      setShowCancelDialog(true)
    } else {
      onCancel?.()
    }
  }, [confirmCancel, onCancel])

  // Confirm cancel
  const confirmCancelAction = useCallback(() => {
    setShowCancelDialog(false)
    onCancel?.()
  }, [onCancel])

  // Handle step click (for stepper navigation)
  const handleStepClick = useCallback(
    (stepIndex: number) => {
      if (allowBackNavigation && stepIndex !== currentStep) {
        // Can navigate to any step if back navigation is allowed
        setCurrentStep(stepIndex)
        setValidationError(undefined)
      } else if (allowBackNavigation && stepIndex < currentStep) {
        // Can navigate back
        setCurrentStep(stepIndex)
        setValidationError(undefined)
      }
    },
    [allowBackNavigation, currentStep]
  )

  // Check if step is valid (for UI feedback)
  const isStepValid = useMemo(() => {
    if (!currentStepData?.validate) return true
    // This is a simple check - actual validation happens on next
    return !validationError
  }, [currentStepData, validationError])

  // Render step content
  const renderStepContent = () => {
    if (!currentStepData) return null

    const StepContent = currentStepData.content

    return (
      <StepContent
        formData={allFormData}
        updateFormData={updateFormData}
        stepIndex={currentStep}
        totalSteps={totalSteps}
        isValid={isStepValid}
        validationError={validationError}
      />
    )
  }

  return (
    <Box className={className} sx={{ width: '100%' }}>
      {/* Progress indicator */}
      {showProgress && (
        <Box sx={{ marginBottom: spacing[4] }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing[1] }}>
            <Typography variant="body2" color="text.secondary">
              Step {currentStep + 1} of {totalSteps}
            </Typography>
            {showProgress && (
              <Typography variant="body2" color="text.secondary">
                {progress}% Complete
              </Typography>
            )}
            {enablePersistence && savedState?.lastSaved && (
              <Typography variant="caption" color="text.secondary">
                Last saved: {new Date(savedState.lastSaved).toLocaleTimeString()}
              </Typography>
            )}
          </Box>
          {showProgressBar && (
            <Box
              sx={{
                width: '100%',
                height: 6,
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
          )}
        </Box>
      )}

      {/* Stepper */}
      <Box sx={{ marginBottom: spacing[6] }}>
        <Stepper
          steps={steps.map((step) => ({
            id: step.id,
            label: step.label,
            description: step.description,
            optional: step.optional,
          }))}
          activeStep={currentStep}
          onStepClick={handleStepClick}
          orientation="horizontal"
        />
      </Box>

      {/* Step content */}
      <Paper
        sx={{
          padding: spacing[4],
          marginBottom: spacing[4],
          minHeight: '400px',
        }}
      >
        {loading || isCompleting ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              minHeight: '300px',
              gap: spacing[2],
            }}
          >
            <CircularProgress />
            <Typography variant="body2" color="text.secondary">
              {isCompleting ? 'Completing...' : 'Loading...'}
            </Typography>
          </Box>
        ) : (
          <>
            {currentStepData?.description && (
              <Typography variant="h6" gutterBottom sx={{ marginBottom: spacing[3] }}>
                {currentStepData.description}
              </Typography>
            )}
            {validationError && (
              <Box
                sx={{
                  padding: spacing[2],
                  marginBottom: spacing[2],
                  backgroundColor: colors.error[50],
                  border: `1px solid ${colors.error[200]}`,
                  borderRadius: 1,
                }}
              >
                <Typography variant="body2" color="error">
                  {validationError}
                </Typography>
              </Box>
            )}
            {renderStepContent()}
          </>
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
            <Button
              onClick={handleBack}
              disabled={validating || loading || isCompleting}
              startIcon={<ArrowBackIcon />}
            >
              Back
            </Button>
          )}
          {onCancel && (
            <Button
              onClick={handleCancel}
              disabled={validating || loading || isCompleting}
              sx={{ marginLeft: spacing[2] }}
              startIcon={<CloseIcon />}
            >
              Cancel
            </Button>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: spacing[2] }}>
          {currentStepData?.skippable && !isLastStep && (
            <Button
              onClick={handleSkip}
              disabled={validating || loading || isCompleting}
              variant="outlined"
            >
              Skip
            </Button>
          )}
          {enablePersistence && (
            <Button
              onClick={saveState}
              disabled={validating || loading || isCompleting}
              variant="outlined"
              startIcon={<SaveIcon />}
            >
              Save Progress
            </Button>
          )}
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={validating || loading || isCompleting}
            endIcon={isLastStep ? undefined : <ArrowForwardIcon />}
          >
            {validating ? (
              <>
                <CircularProgress size={16} sx={{ marginRight: 1 }} />
                Validating...
              </>
            ) : isCompleting ? (
              <>
                <CircularProgress size={16} sx={{ marginRight: 1 }} />
                Completing...
              </>
            ) : isLastStep ? (
              'Complete'
            ) : (
              'Next'
            )}
          </Button>
        </Box>
      </Box>

      {/* Cancel confirmation dialog */}
      <Dialog open={showCancelDialog} onClose={() => setShowCancelDialog(false)}>
        <DialogTitle>Cancel Wizard?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {enablePersistence
              ? 'Your progress has been saved. You can resume later. Are you sure you want to cancel?'
              : 'Are you sure you want to cancel? Your progress will be lost.'}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowCancelDialog(false)}>Continue</Button>
          <Button onClick={confirmCancelAction} color="error" variant="contained">
            Cancel Wizard
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

Wizard.displayName = 'Wizard'

