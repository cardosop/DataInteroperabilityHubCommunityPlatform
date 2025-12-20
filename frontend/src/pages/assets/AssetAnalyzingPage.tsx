/**
 * Asset Analyzing Page
 *
 * Progress tracking page for data-first onboarding flow
 * Implements UI-DPO-003: Analyzing Data
 *
 * Shows real-time progress of:
 * 1. Upload file
 * 2. Infer schema
 * 3. Run data quality checks
 * 4. Run compliance checks
 * 5. Prepare contract draft
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Paper,
  CircularProgress,
  Alert,
  Button,
  LinearProgress,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material'
import { Stepper } from '@/components/navigation/Stepper'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useJobStatus } from '@/hooks/useJobs'
import { useDataset } from '@/hooks/useDatasets'

/**
 * Analysis step status
 */
type StepStatus = 'pending' | 'in-progress' | 'completed' | 'error'

/**
 * Analysis step definition
 */
interface AnalysisStep {
  id: string
  label: string
  description: string
  status: StepStatus
  jobId?: string
  error?: string
}

/**
 * Asset Analyzing Page Component
 */
export const AssetAnalyzingPage: React.FC = () => {
  const { datasetId } = useParams<{ datasetId: string }>()
  const navigate = useNavigate()

  // Step states
  const [steps, setSteps] = useState<AnalysisStep[]>([
    {
      id: 'upload',
      label: 'Upload file',
      description: 'File uploaded successfully',
      status: 'completed',
    },
    {
      id: 'infer-schema',
      label: 'Infer schema',
      description: 'Analyzing data structure...',
      status: 'in-progress',
    },
    {
      id: 'dq-checks',
      label: 'Run data quality checks',
      description: 'Waiting for schema inference...',
      status: 'pending',
    },
    {
      id: 'compliance-checks',
      label: 'Run compliance checks',
      description: 'Waiting for previous steps...',
      status: 'pending',
    },
    {
      id: 'prepare-contract',
      label: 'Prepare contract draft',
      description: 'Waiting for previous steps...',
      status: 'pending',
    },
  ])

  const [currentStepIndex, setCurrentStepIndex] = useState(1)
  const [overallError, setOverallError] = useState<string | null>(null)
  const [canNavigateAway, setCanNavigateAway] = useState(true)

  // Fetch dataset to get job IDs
  const { data: dataset } = useDataset(datasetId || null)

  // WebSocket for real-time updates
  const { isConnected, subscribe } = useWebSocket(
    [
      'job.started',
      'job.completed',
      'job.failed',
      'job.progress',
      'asset.workflow.progress',
    ],
    useCallback((event) => {
      // Handle job events
      if (event.event_type.startsWith('job.')) {
        const jobId = (event.data as any).job_id
        const jobType = (event.data as any).job_type

        // Update step based on job type
        setSteps((prevSteps) => {
          const newSteps = [...prevSteps]
          const stepIndex = newSteps.findIndex((s) => s.jobId === jobId)

          if (stepIndex >= 0) {
            if (event.event_type === 'job.completed') {
              newSteps[stepIndex].status = 'completed'
              newSteps[stepIndex].description = 'Completed successfully'
              // Move to next step
              if (stepIndex < newSteps.length - 1) {
                newSteps[stepIndex + 1].status = 'in-progress'
                setCurrentStepIndex(stepIndex + 1)
              }
            } else if (event.event_type === 'job.failed') {
              newSteps[stepIndex].status = 'error'
              newSteps[stepIndex].error = (event.data as any).error_message || 'Job failed'
              setOverallError('Analysis failed. Please try again.')
            } else if (event.event_type === 'job.progress') {
              const progress = (event.data as any).progress || 0
              newSteps[stepIndex].description = `Progress: ${progress}%`
            }
          }

          return newSteps
        })
      }

      // Handle workflow progress events
      if (event.event_type === 'asset.workflow.progress') {
        const workflowData = event.data as any
        const currentStep = workflowData.current_step
        const progress = workflowData.progress || 0

        setSteps((prevSteps) => {
          const newSteps = [...prevSteps]
          const stepIndex = newSteps.findIndex((s) => s.id === currentStep)

          if (stepIndex >= 0) {
            newSteps[stepIndex].status = 'in-progress'
            newSteps[stepIndex].description = `Progress: ${progress}%`
            setCurrentStepIndex(stepIndex)
          }

          return newSteps
        })
      }
    }, [])
  )

  // Calculate overall progress
  const overallProgress = useMemo(() => {
    const completedSteps = steps.filter((s) => s.status === 'completed').length
    return (completedSteps / steps.length) * 100
  }, [steps])

  // Check if analysis is complete
  const isComplete = useMemo(() => {
    return steps.every((s) => s.status === 'completed' || s.status === 'error')
  }, [steps])

  // Navigate to contract editor when complete
  useEffect(() => {
    if (isComplete && !overallError) {
      // Find asset ID from workflow or navigate to assets list
      // For now, navigate to assets list - in real implementation, would get asset ID
      const timer = setTimeout(() => {
        navigate('/assets')
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [isComplete, overallError, navigate])

  // Get current step status message
  const currentStepMessage = useMemo(() => {
    const currentStep = steps[currentStepIndex]
    if (!currentStep) return 'Processing...'

    switch (currentStep.status) {
      case 'in-progress':
        return currentStep.description || `Processing: ${currentStep.label}...`
      case 'completed':
        return `Completed: ${currentStep.label}`
      case 'error':
        return `Error: ${currentStep.error || 'Unknown error'}`
      default:
        return `Waiting: ${currentStep.label}`
    }
  }, [steps, currentStepIndex])

  return (
    <Container maxWidth="md">
      <Box sx={{ py: 4 }}>
        <Typography variant="h4" gutterBottom>
          Analyzing Data
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
          We're analyzing your data and preparing a contract. This may take a few minutes.
        </Typography>

        {/* Error State */}
        {overallError && (
          <Alert
            severity="error"
            sx={{ mb: 4 }}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  setOverallError(null)
                  // Retry logic would go here
                }}
              >
                Retry
              </Button>
            }
          >
            {overallError}
          </Alert>
        )}

        {/* Progress Stepper */}
        <Paper sx={{ p: 4, mb: 4 }}>
          <Stepper
            steps={steps.map((step) => ({
              id: step.id,
              label: step.label,
              description: step.description,
            }))}
            activeStep={currentStepIndex}
            orientation="vertical"
          />
        </Paper>

        {/* Progress Indicator */}
        <Paper sx={{ p: 4, mb: 4 }}>
          <Box sx={{ textAlign: 'center' }}>
            <CircularProgress
              size={80}
              variant="determinate"
              value={overallProgress}
              sx={{ mb: 3 }}
            />
            <Typography variant="h6" gutterBottom>
              {currentStepMessage}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {Math.round(overallProgress)}% complete
            </Typography>
            <LinearProgress
              variant="determinate"
              value={overallProgress}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        </Paper>

        {/* Background Processing Note */}
        <Alert severity="info">
          <Typography variant="body2">
            <strong>Note:</strong> You can navigate away from this page. The analysis will
            continue in the background, and you'll be notified when it's complete.
          </Typography>
        </Alert>

        {/* Navigation */}
        <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
          <Button
            variant="outlined"
            onClick={() => navigate('/assets')}
          >
            View Assets
          </Button>
          {isComplete && !overallError && (
            <Button
              variant="contained"
              startIcon={<CheckCircleIcon />}
              onClick={() => navigate('/assets')}
            >
              Continue to Assets
            </Button>
          )}
        </Box>
      </Box>
    </Container>
  )
}

