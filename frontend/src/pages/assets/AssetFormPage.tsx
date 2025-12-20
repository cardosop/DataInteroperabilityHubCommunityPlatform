/**
 * Asset Form Page
 *
 * Comprehensive asset creation/editing page with onboarding flows:
 * - Data-First Flow: Upload data → Analyze → Create contract
 * - Contract-First Flow: Create contract → Attach dataset
 * - Contract-Only Flow: Create contract only
 *
 * Implements UI-DPO-001: Asset Creation
 */

import React, { useState, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Paper,
  Button,
  Alert,
} from '@mui/material'
import { ArrowBack as ArrowBackIcon } from '@mui/icons-material'
import { Wizard, type WizardStep } from '@/components/forms/Wizard'
import { useCreateAsset } from '@/hooks/useAssets'
import { AssetMetadataStep } from './steps/AssetMetadataStep'
import { FileUploadStep } from './steps/FileUploadStep'
import { ContractUploadStep } from './steps/ContractUploadStep'
import { SchemaComparisonStep } from './steps/SchemaComparisonStep'
import { AssetActivationStep } from './steps/AssetActivationStep'
import type { CreateAssetRequest } from '@/lib/api/assets'

/**
 * Onboarding mode type
 */
export type OnboardingMode = 'data-first' | 'contract-first' | 'contract-only'

/**
 * Asset form data structure
 */
export interface AssetFormData {
  // Basic metadata
  name: string
  key: string
  description: string
  domain: string | null
  tags: string[]
  visibility: 'INTERNAL' | 'PUBLIC'

  // Onboarding mode
  onboardingMode: OnboardingMode

  // Data-first flow
  uploadedFile?: File
  fileId?: string
  datasetId?: string
  workflowInstanceId?: string

  // Contract-first flow
  contractId?: string
  contractData?: any

  // Contract-only flow
  contractOnlyData?: any
}

/**
 * Asset Form Page Component
 */
export const AssetFormPage: React.FC = () => {
  const navigate = useNavigate()
  const { id } = useParams<{ id?: string }>()
  const isEditMode = !!id

  // Form state
  const [formData, setFormData] = useState<AssetFormData>({
    name: '',
    key: '',
    description: '',
    domain: null,
    tags: [],
    visibility: 'INTERNAL',
    onboardingMode: 'data-first',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  // Asset creation mutation
  const createAsset = useCreateAsset()

  // Update form data
  const updateFormData = useCallback((updates: Partial<AssetFormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }))
    // Clear errors for updated fields
    const updatedFields = Object.keys(updates)
    setErrors((prev) => {
      const newErrors = { ...prev }
      updatedFields.forEach((field) => {
        delete newErrors[field]
      })
      return newErrors
    })
  }, [])

  // Auto-generate key from name
  const generateKey = useCallback((name: string): string => {
    return name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .substring(0, 255)
  }, [])

  // Handle name change with auto-key generation
  const handleNameChange = useCallback(
    (name: string) => {
      updateFormData({ name })
      if (!formData.key || formData.key === generateKey(formData.name)) {
        updateFormData({ key: generateKey(name) })
      }
    },
    [formData.key, formData.name, generateKey, updateFormData]
  )

  // Validate step 1 (metadata)
  const validateMetadata = useCallback((): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) {
      newErrors.name = 'Asset name is required'
    }

    if (!formData.key.trim()) {
      newErrors.key = 'Asset key is required'
    } else if (!/^[a-z0-9-]+$/.test(formData.key)) {
      newErrors.key = 'Key must contain only lowercase letters, numbers, and hyphens'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }, [formData])

  // Create asset record
  const handleCreateAsset = useCallback(async (): Promise<string> => {
    if (!validateMetadata()) {
      throw new Error('Please fix validation errors')
    }

    const assetData: CreateAssetRequest = {
      key: formData.key,
      name: formData.name,
      description: formData.description || null,
      domain: formData.domain || null,
      visibility: formData.visibility,
    }

    const asset = await createAsset.mutateAsync(assetData)
    return asset.id
  }, [formData, validateMetadata, createAsset])

  // Build wizard steps based on onboarding mode
  const wizardSteps = useMemo((): WizardStep[] => {
    const steps: WizardStep[] = []

    // Step 1: Basic Metadata + Onboarding Mode Selection
    steps.push({
      label: 'Basic Information',
      description: 'Provide asset metadata and select onboarding mode',
      content: (
        <AssetMetadataStep
          formData={formData}
          onUpdate={updateFormData}
          onNameChange={handleNameChange}
          errors={errors}
        />
      ),
      validate: validateMetadata,
    })

    // Step 2: Mode-specific steps
    if (formData.onboardingMode === 'data-first') {
      // Data-First Flow: File Upload
      steps.push({
        label: 'Upload Data File',
        description: 'Upload your data file for analysis',
        content: (
          <FileUploadStep
            formData={formData}
            onUpdate={updateFormData}
            onCreateAsset={handleCreateAsset}
          />
        ),
        validate: () => {
          if (!formData.uploadedFile && !formData.fileId) {
            setErrors({ file: 'Please upload a data file' })
            return false
          }
          return true
        },
      })
    } else if (formData.onboardingMode === 'contract-first') {
      // Contract-First Flow: Contract Creation/Upload
      steps.push({
        label: 'Create Contract',
        description: 'Create or upload a contract',
        content: (
          <ContractUploadStep
            formData={formData}
            onUpdate={updateFormData}
            onCreateAsset={handleCreateAsset}
          />
        ),
        validate: () => {
          if (!formData.contractId && !formData.contractData) {
            setErrors({ contract: 'Please create or upload a contract' })
            return false
          }
          return true
        },
      })

      // Schema Comparison (if dataset exists)
      if (formData.datasetId) {
        steps.push({
          label: 'Schema Comparison',
          description: 'Compare inferred schema with contract schema',
          content: (
            <SchemaComparisonStep
              formData={formData}
              onUpdate={updateFormData}
            />
          ),
          optional: true,
        })
      }

      // Dataset Attachment
      steps.push({
        label: 'Attach Dataset',
        description: 'Upload and attach dataset to contract',
        content: (
          <FileUploadStep
            formData={formData}
            onUpdate={updateFormData}
            onCreateAsset={handleCreateAsset}
            isContractFirst={true}
          />
        ),
        validate: () => {
          if (!formData.uploadedFile && !formData.fileId) {
            setErrors({ file: 'Please upload a dataset file' })
            return false
          }
          return true
        },
      })
    } else if (formData.onboardingMode === 'contract-only') {
      // Contract-Only Flow: Contract Creation/Upload
      steps.push({
        label: 'Create Contract',
        description: 'Create or upload a contract',
        content: (
          <ContractUploadStep
            formData={formData}
            onUpdate={updateFormData}
            onCreateAsset={handleCreateAsset}
            isContractOnly={true}
          />
        ),
        validate: () => {
          if (!formData.contractId && !formData.contractData) {
            setErrors({ contract: 'Please create or upload a contract' })
            return false
          }
          return true
        },
      })
    }

    // Final step: Activation (for all flows)
    if (formData.onboardingMode !== 'contract-only' || formData.contractId) {
      steps.push({
        label: 'Review & Activate',
        description: 'Review asset details and activate',
        content: (
          <AssetActivationStep
            formData={formData}
            onUpdate={updateFormData}
          />
        ),
        optional: true,
      })
    }

    return steps
  }, [
    formData,
    updateFormData,
    handleNameChange,
    validateMetadata,
    handleCreateAsset,
    errors,
  ])

  // Handle wizard completion
  const handleComplete = useCallback(
    async (data: Record<string, unknown>) => {
      try {
        // Navigate based on flow
        if (formData.onboardingMode === 'data-first' && formData.datasetId) {
          // For data-first flow, navigate to analyzing page
          // The workflow instance ID will be tracked via the dataset/job
          navigate(`/assets/analyzing/${formData.datasetId}`)
        } else if (formData.contractId) {
          // Navigate to contract editor
          navigate(`/contracts/${formData.contractId}/edit`)
        } else {
          // Navigate to asset detail
          const assetId = formData.workflowInstanceId || await handleCreateAsset()
          navigate(`/assets/${assetId}`)
        }
      } catch (error) {
        console.error('Failed to complete asset creation:', error)
        setErrors({ general: error instanceof Error ? error.message : 'Failed to create asset' })
      }
    },
    [formData, navigate, handleCreateAsset]
  )

  // Handle cancel
  const handleCancel = useCallback(() => {
    if (window.confirm('Are you sure you want to cancel? Unsaved changes will be lost.')) {
      navigate('/assets')
    }
  }, [navigate])

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={handleCancel}
            variant="text"
          >
            Back
          </Button>
          <Typography variant="h4">
            {isEditMode ? 'Edit Asset' : 'Create New Asset'}
          </Typography>
        </Box>

        {/* Error Alert */}
        {errors.general && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {errors.general}
          </Alert>
        )}

        {/* Wizard */}
        <Paper sx={{ p: 4 }}>
          <Wizard
            steps={wizardSteps}
            onComplete={handleComplete}
            onCancel={handleCancel}
            allowBackNavigation={true}
            showProgress={true}
            loading={createAsset.isPending}
          />
        </Paper>
      </Box>
    </Container>
  )
}

