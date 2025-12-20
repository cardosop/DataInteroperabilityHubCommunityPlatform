/**
 * Contract Form Page
 *
 * Comprehensive contract creation/editing page with:
 * - Contract form (name, description, format)
 * - Contract editor (JSON/YAML)
 * - Contract validation
 * - Contract publishing
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Paper,
  Button,
  Alert,
  Tabs,
  Tab,
  Divider,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  Save as SaveIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Publish as PublishIcon,
  Code as CodeIcon,
} from '@mui/icons-material'
import { useContract } from '@/hooks/useContract'
import { useCreateContract } from '@/hooks/useCreateContract'
import { useUpdateContract } from '@/hooks/useUpdateContract'
import { useValidateContract } from '@/hooks/useValidateContract'
import { usePublishContract } from '@/hooks/usePublishContract'
import { TextInput } from '@/components/forms/TextInput'
import { Textarea } from '@/components/forms/Textarea'
import { FileUpload } from '@/components/forms/FileUpload'
import { Badge } from '@/components/data-display/Badge'
import { CodeBlock } from '@/components/data-display/CodeBlock'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import type { Contract, ContractStatus, ValidationStatus } from '@/lib/api/contracts'

/**
 * Contract form data structure
 */
export interface ContractFormData {
  name: string | null
  description: string | null
  original_raw: string
  original_format: 'JSON' | 'YAML'
  asset_id: string | null
}

/**
 * Contract Form Page Component
 */
export const ContractFormPage: React.FC = () => {
  const navigate = useNavigate()
  const { id } = useParams<{ id?: string }>()
  const isEditMode = !!id
  const { showToast } = useToastManager()

  // Form state
  const [formData, setFormData] = useState<ContractFormData>({
    name: null,
    description: null,
    original_raw: '',
    original_format: 'JSON',
    asset_id: null,
  })

  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isDirty, setIsDirty] = useState(false)
  const [showValidationDialog, setShowValidationDialog] = useState(false)
  const [showPublishDialog, setShowPublishDialog] = useState(false)
  const [editorTab, setEditorTab] = useState<'editor' | 'preview'>('editor')

  // Fetch contract if editing
  const {
    data: contract,
    isLoading: isLoadingContract,
    error: contractError,
  } = useContract(id || '', { enabled: isEditMode && !!id })

  // Mutations
  const createContract = useCreateContract()
  const updateContract = useUpdateContract()
  const validateContract = useValidateContract()
  const publishContract = usePublishContract()

  // Validation result state
  const [validationResult, setValidationResult] = useState<{
    status: ValidationStatus
    errors: Array<{ field?: string; message: string }>
    warnings: Array<{ field?: string; message: string }>
  } | null>(null)

  // Initialize form data from contract
  useEffect(() => {
    if (contract && isEditMode) {
      setFormData({
        name: contract.hub_contract_json?.info?.name || null,
        description: contract.hub_contract_json?.info?.description || null,
        original_raw: contract.original_raw || JSON.stringify(contract.hub_contract_json, null, 2),
        original_format: (contract.original_format as 'JSON' | 'YAML') || 'JSON',
        asset_id: contract.asset_id || null,
      })
      setIsDirty(false)
    }
  }, [contract, isEditMode])

  // Update form data
  const updateFormData = useCallback((updates: Partial<ContractFormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }))
    setIsDirty(true)
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

  // Validate contract content
  const validateContractContent = useCallback(async (): Promise<boolean> => {
    if (!formData.original_raw.trim()) {
      setErrors({ original_raw: 'Contract content is required' })
      return false
    }

    // Try to parse JSON/YAML
    try {
      if (formData.original_format === 'JSON') {
        JSON.parse(formData.original_raw)
      }
      // YAML parsing would require a library, so we'll skip client-side validation for YAML
    } catch (error) {
      setErrors({
        original_raw: `Invalid ${formData.original_format} format: ${error instanceof Error ? error.message : 'Parse error'}`,
      })
      return false
    }

    return true
  }, [formData])

  // Handle contract validation
  const handleValidate = useCallback(async () => {
    if (!id) {
      showToast({
        message: 'Please save the contract first before validating',
        severity: 'warning',
      })
      return
    }

    try {
      const result = await validateContract.mutateAsync({
        id,
        data: { async: false },
      })

      setValidationResult({
        status: result.validation_status,
        errors: result.errors || [],
        warnings: result.warnings || [],
      })
      setShowValidationDialog(true)

      if (result.validation_status === 'VALID') {
        showToast({
          message: 'Contract validation passed',
          severity: 'success',
        })
      } else {
        showToast({
          message: `Contract validation failed: ${result.errors?.length || 0} error(s), ${result.warnings?.length || 0} warning(s)`,
          severity: 'warning',
        })
      }
    } catch (error) {
      showToast({
        message: error instanceof Error ? error.message : 'Validation failed',
        severity: 'error',
      })
    }
  }, [id, validateContract, showToast])

  // Handle contract save
  const handleSave = useCallback(async () => {
    // Validate form
    if (!(await validateContractContent())) {
      return
    }

    try {
      if (isEditMode && id) {
        // Update existing contract
        const updatedContract = await updateContract.mutateAsync({
          id,
          data: {
            original_raw: formData.original_raw,
            original_format: formData.original_format,
          },
        })

        showToast({
          message: 'Contract updated successfully',
          severity: 'success',
        })
        setIsDirty(false)
        navigate(`/contracts/${id}`)
      } else {
        // Create new contract
        const newContract = await createContract.mutateAsync({
          original_raw: formData.original_raw,
          original_format: formData.original_format,
          name: formData.name,
          description: formData.description,
          asset_id: formData.asset_id,
        })

        showToast({
          message: 'Contract created successfully',
          severity: 'success',
        })
        navigate(`/contracts/${newContract.id}`)
      }
    } catch (error) {
      showToast({
        message: error instanceof Error ? error.message : 'Failed to save contract',
        severity: 'error',
      })
    }
  }, [
    isEditMode,
    id,
    formData,
    validateContractContent,
    createContract,
    updateContract,
    showToast,
    navigate,
  ])

  // Handle contract publish
  const handlePublish = useCallback(async () => {
    if (!id) {
      showToast({
        message: 'Please save the contract first before publishing',
        severity: 'warning',
      })
      return
    }

    try {
      await publishContract.mutateAsync({
        id,
        data: {},
      })

      showToast({
        message: 'Contract published successfully',
        severity: 'success',
      })
      setShowPublishDialog(false)
      navigate(`/contracts/${id}`)
    } catch (error) {
      showToast({
        message: error instanceof Error ? error.message : 'Failed to publish contract',
        severity: 'error',
      })
    }
  }, [id, publishContract, showToast, navigate])

  // Handle file upload
  const handleFileUpload = useCallback(async (file: File) => {
    try {
      const text = await file.text()
      const fileName = file.name.toLowerCase()

      // Determine format from file extension
      let format: 'JSON' | 'YAML' = 'JSON'
      if (fileName.endsWith('.yaml') || fileName.endsWith('.yml')) {
        format = 'YAML'
      }

      // Try to parse JSON if JSON format
      if (format === 'JSON') {
        try {
          JSON.parse(text)
        } catch (e) {
          setErrors({ original_raw: 'Invalid JSON file' })
          return
        }
      }

      updateFormData({
        original_raw: text,
        original_format: format,
      })

      showToast({
        message: 'Contract file uploaded successfully',
        severity: 'success',
      })
    } catch (error) {
      showToast({
        message: error instanceof Error ? error.message : 'Failed to upload file',
        severity: 'error',
      })
    }
  }, [updateFormData, showToast])

  // Format contract for preview
  const formattedContract = useMemo(() => {
    if (!formData.original_raw.trim()) return ''
    try {
      if (formData.original_format === 'JSON') {
        const parsed = JSON.parse(formData.original_raw)
        return JSON.stringify(parsed, null, 2)
      }
      return formData.original_raw
    } catch {
      return formData.original_raw
    }
  }, [formData.original_raw, formData.original_format])

  // Loading state
  if (isEditMode && isLoadingContract) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading contract..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (isEditMode && contractError) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load contract"
            message={contractError.message || 'An error occurred while loading the contract.'}
            onRetry={() => window.location.reload()}
          />
        </Box>
      </Container>
    )
  }

  const isSaving = createContract.isPending || updateContract.isPending
  const isValidating = validateContract.isPending
  const isPublishing = publishContract.isPending

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate('/contracts')}
              sx={{ mb: 2 }}
            >
              Back to Contracts
            </Button>
            <Typography variant="h4" gutterBottom>
              {isEditMode ? 'Edit Contract' : 'Create Contract'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {isEditMode
                ? 'Update contract content and settings'
                : 'Create a new data contract in JSON or YAML format'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {isEditMode && id && (
              <>
                <Button
                  variant="outlined"
                  startIcon={<CheckCircleIcon />}
                  onClick={handleValidate}
                  disabled={isValidating}
                >
                  {isValidating ? 'Validating...' : 'Validate'}
                </Button>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<PublishIcon />}
                  onClick={() => setShowPublishDialog(true)}
                  disabled={isPublishing || contract?.status === 'ACTIVE'}
                >
                  {isPublishing ? 'Publishing...' : 'Publish'}
                </Button>
              </>
            )}
          </Box>
        </Box>

        {/* Contract Status (if editing) */}
        {isEditMode && contract && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Status
                </Typography>
                <Box sx={{ mt: 0.5 }}>
                  <Badge
                    variant={
                      contract.status === 'ACTIVE'
                        ? 'success'
                        : contract.status === 'DRAFT'
                        ? 'info'
                        : 'neutral'
                    }
                    size="sm"
                  >
                    {contract.status}
                  </Badge>
                </Box>
              </Box>
              {contract.validation_status && (
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Validation
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Badge
                      variant={
                        contract.validation_status === 'VALID'
                          ? 'success'
                          : contract.validation_status === 'WARNING_ONLY'
                          ? 'warning'
                          : 'error'
                      }
                      size="sm"
                    >
                      {contract.validation_status}
                    </Badge>
                  </Box>
                </Box>
              )}
              {contract.normalization_status && (
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Normalization
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Badge
                      variant={
                        contract.normalization_status === 'NORMALIZED_OK'
                          ? 'success'
                          : contract.normalization_status === 'NORMALIZED_WITH_WARNINGS'
                          ? 'warning'
                          : contract.normalization_status === 'NORMALIZATION_FAILED'
                          ? 'error'
                          : 'neutral'
                      }
                      size="sm"
                    >
                      {contract.normalization_status.replace(/_/g, ' ')}
                    </Badge>
                  </Box>
                </Box>
              )}
            </Box>
          </Paper>
        )}

        {/* Form */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Contract Information
          </Typography>
          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <TextInput
              label="Contract Name"
              value={formData.name || ''}
              onChange={(value) => updateFormData({ name: value || null })}
              placeholder="e.g., Customer Data Contract"
              helperText="Optional: Name for the contract (auto-generated if not provided)"
              error={errors.name}
            />

            <Textarea
              label="Description"
              value={formData.description || ''}
              onChange={(value) => updateFormData({ description: value || null })}
              rows={3}
              placeholder="Describe the contract..."
              helperText="Optional: Description of the contract"
              error={errors.description}
            />

            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Contract Format
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
                <Button
                  variant={formData.original_format === 'JSON' ? 'contained' : 'outlined'}
                  onClick={() => updateFormData({ original_format: 'JSON' })}
                >
                  JSON
                </Button>
                <Button
                  variant={formData.original_format === 'YAML' ? 'contained' : 'outlined'}
                  onClick={() => updateFormData({ original_format: 'YAML' })}
                >
                  YAML
                </Button>
              </Box>
            </Box>
          </Box>
        </Paper>

        {/* Contract Editor */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">Contract Content</Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                variant={editorTab === 'editor' ? 'contained' : 'outlined'}
                onClick={() => setEditorTab('editor')}
                startIcon={<CodeIcon />}
              >
                Editor
              </Button>
              <Button
                size="small"
                variant={editorTab === 'preview' ? 'contained' : 'outlined'}
                onClick={() => setEditorTab('preview')}
              >
                Preview
              </Button>
            </Box>
          </Box>
          <Divider sx={{ mb: 2 }} />

          {editorTab === 'editor' ? (
            <Box>
              <Textarea
                label="Contract Content"
                value={formData.original_raw}
                onChange={(value) => updateFormData({ original_raw: value })}
                rows={20}
                placeholder={
                  formData.original_format === 'JSON'
                    ? '{\n  "hub_contract_version": "1.0.0",\n  ...\n}'
                    : 'hub_contract_version: "1.0.0"\n...'
                }
                helperText={`Enter contract content in ${formData.original_format} format`}
                error={errors.original_raw}
                style={{
                  fontFamily: 'monospace',
                  fontSize: '14px',
                }}
              />

              <Box sx={{ mt: 2 }}>
                <FileUpload
                  accept={formData.original_format === 'JSON' ? '.json' : '.yaml,.yml'}
                  maxSize={10 * 1024 * 1024} // 10MB
                  onUpload={handleFileUpload}
                />
              </Box>
            </Box>
          ) : (
            <Box>
              <CodeBlock
                code={formattedContract || 'No content to preview'}
                language={formData.original_format.toLowerCase()}
                showCopy
              />
            </Box>
          )}
        </Paper>

        {/* Actions */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Button
            variant="outlined"
            onClick={() => {
              if (isDirty) {
                if (window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
                  navigate('/contracts')
                }
              } else {
                navigate('/contracts')
              }
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={isSaving ? <CircularProgress size={16} /> : <SaveIcon />}
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? 'Saving...' : isEditMode ? 'Update Contract' : 'Create Contract'}
          </Button>
        </Box>

        {/* Validation Dialog */}
        <Dialog open={showValidationDialog} onClose={() => setShowValidationDialog(false)} maxWidth="md" fullWidth>
          <DialogTitle>Validation Results</DialogTitle>
          <DialogContent>
            {validationResult && (
              <Box>
                <Box sx={{ mb: 2 }}>
                  <Badge
                    variant={
                      validationResult.status === 'VALID'
                        ? 'success'
                        : validationResult.status === 'WARNING_ONLY'
                        ? 'warning'
                        : 'error'
                    }
                    size="md"
                  >
                    {validationResult.status}
                  </Badge>
                </Box>

                {validationResult.errors.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" color="error" gutterBottom>
                      Errors ({validationResult.errors.length})
                    </Typography>
                    <List dense>
                      {validationResult.errors.map((error, index) => (
                        <ListItem key={index}>
                          <ListItemIcon>
                            <ErrorIcon color="error" />
                          </ListItemIcon>
                          <ListItemText
                            primary={error.message}
                            secondary={error.field ? `Field: ${error.field}` : undefined}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}

                {validationResult.warnings.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" color="warning.main" gutterBottom>
                      Warnings ({validationResult.warnings.length})
                    </Typography>
                    <List dense>
                      {validationResult.warnings.map((warning, index) => (
                        <ListItem key={index}>
                          <ListItemIcon>
                            <WarningIcon color="warning" />
                          </ListItemIcon>
                          <ListItemText
                            primary={warning.message}
                            secondary={warning.field ? `Field: ${warning.field}` : undefined}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowValidationDialog(false)}>Close</Button>
          </DialogActions>
        </Dialog>

        {/* Publish Dialog */}
        <Dialog open={showPublishDialog} onClose={() => setShowPublishDialog(false)}>
          <DialogTitle>Publish Contract</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to publish this contract? Published contracts are made available to other tenants
              in the marketplace.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowPublishDialog(false)}>Cancel</Button>
            <Button onClick={handlePublish} variant="contained" disabled={isPublishing}>
              {isPublishing ? 'Publishing...' : 'Publish'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

