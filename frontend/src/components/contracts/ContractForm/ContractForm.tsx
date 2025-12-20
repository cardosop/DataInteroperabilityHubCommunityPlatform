/**
 * Contract Form Component
 *
 * Form component for creating and editing contracts.
 * Uses react-hook-form for form management and validation.
 */

import React, { useEffect } from 'react'
import { useForm, FormProvider } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Box,
  Paper,
  Typography,
  Divider,
  Tabs,
  Tab,
  Button,
  ButtonGroup,
} from '@mui/material'
import type { Contract, CreateContractRequest, UpdateContractRequest } from '@/lib/api/contracts'
import { FormField } from '@/components/forms/FormField'
import { FormSection } from '@/components/forms/FormSection'
import { FormActions } from '@/components/forms/FormActions'
import { Textarea } from '@/components/forms/Textarea'
import { FileUpload } from '@/components/forms/FileUpload'
import { CodeBlock } from '@/components/data-display/CodeBlock'

// Validation schema
const contractFormSchema = z.object({
  name: z
    .string()
    .max(255, 'Name must be 255 characters or less')
    .nullable()
    .optional(),
  description: z
    .string()
    .max(5000, 'Description must be 5000 characters or less')
    .nullable()
    .optional(),
  original_raw: z
    .string()
    .min(1, 'Contract content is required'),
  original_format: z.enum(['JSON', 'YAML']),
  asset_id: z
    .string()
    .uuid('Asset ID must be a valid UUID')
    .nullable()
    .optional(),
})

export type ContractFormData = z.infer<typeof contractFormSchema>

export interface ContractFormProps {
  /**
   * Existing contract data (for edit mode)
   */
  contract?: Contract
  /**
   * Loading state
   * @default false
   */
  loading?: boolean
  /**
   * Submit button label
   * @default 'Save'
   */
  submitLabel?: string
  /**
   * Show cancel button
   * @default true
   */
  showCancel?: boolean
  /**
   * Cancel button label
   * @default 'Cancel'
   */
  cancelLabel?: string
  /**
   * Callback when form is submitted
   */
  onSubmit: (data: CreateContractRequest | UpdateContractRequest) => void | Promise<void>
  /**
   * Callback when form is cancelled
   */
  onCancel?: () => void
  /**
   * Form mode
   * @default 'create'
   */
  mode?: 'create' | 'edit'
  /**
   * Show editor tabs (editor/preview)
   * @default true
   */
  showEditorTabs?: boolean
}

/**
 * Contract Form Component
 *
 * @example
 * ```tsx
 * <ContractForm
 *   contract={contract}
 *   mode="edit"
 *   onSubmit={async (data) => {
 *     await updateContract.mutateAsync({ id: contract.id, data })
 *   }}
 *   onCancel={() => navigate('/contracts')}
 * />
 * ```
 */
export const ContractForm: React.FC<ContractFormProps> = ({
  contract,
  loading = false,
  submitLabel = 'Save',
  showCancel = true,
  cancelLabel = 'Cancel',
  onSubmit,
  onCancel,
  mode = 'create',
  showEditorTabs = true,
}) => {
  const form = useForm<ContractFormData>({
    resolver: zodResolver(contractFormSchema),
    defaultValues: {
      name: null,
      description: null,
      original_raw: '',
      original_format: 'JSON',
      asset_id: null,
    },
    mode: 'onBlur',
  })

  const { handleSubmit, reset, watch, setValue } = form
  const [editorTab, setEditorTab] = React.useState<'editor' | 'preview'>('editor')

  const originalRaw = watch('original_raw')
  const originalFormat = watch('original_format')

  // Reset form when contract changes
  useEffect(() => {
    if (contract) {
      reset({
        name: contract.hub_contract_json?.info?.name || null,
        description: contract.hub_contract_json?.info?.description || null,
        original_raw: contract.original_raw || JSON.stringify(contract.hub_contract_json, null, 2),
        original_format: (contract.original_format as 'JSON' | 'YAML') || 'JSON',
        asset_id: contract.asset_id || null,
      })
    }
  }, [contract, reset])

  // Format contract for preview
  const formattedContract = React.useMemo(() => {
    if (!originalRaw.trim()) return ''
    try {
      if (originalFormat === 'JSON') {
        const parsed = JSON.parse(originalRaw)
        return JSON.stringify(parsed, null, 2)
      }
      return originalRaw
    } catch {
      return originalRaw
    }
  }, [originalRaw, originalFormat])

  const handleFormSubmit = async (data: ContractFormData) => {
    if (mode === 'edit' && contract) {
      const updateData: UpdateContractRequest = {
        original_raw: data.original_raw,
        original_format: data.original_format,
      }
      await onSubmit(updateData)
    } else {
      const createData: CreateContractRequest = {
        original_raw: data.original_raw,
        original_format: data.original_format,
        name: data.name,
        description: data.description,
        asset_id: data.asset_id,
      }
      await onSubmit(createData)
    }
  }

  const handleCancel = () => {
    if (onCancel) {
      onCancel()
    } else {
      reset()
    }
  }

  const handleFileUpload = async (file: File) => {
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
          form.setError('original_raw', {
            type: 'manual',
            message: 'Invalid JSON file',
          })
          return
        }
      }

      setValue('original_raw', text)
      setValue('original_format', format)
    } catch (error) {
      form.setError('original_raw', {
        type: 'manual',
        message: error instanceof Error ? error.message : 'Failed to upload file',
      })
    }
  }

  return (
    <FormProvider {...form}>
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            {mode === 'edit' ? 'Edit Contract' : 'Create Contract'}
          </Typography>
          <Divider sx={{ my: 2 }} />

          <FormSection title="Basic Information">
            <FormField
              name="name"
              label="Contract Name"
              type="text"
              helperText="Optional: Name for the contract (auto-generated if not provided)"
            />

            <FormField
              name="description"
              label="Description"
              type="textarea"
              multiline
              rows={3}
              helperText="Optional: Description of the contract"
            />

            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Contract Format
              </Typography>
              <Box sx={{ mt: 1 }}>
                <ButtonGroup>
                  <Button
                    variant={originalFormat === 'JSON' ? 'contained' : 'outlined'}
                    onClick={() => setValue('original_format', 'JSON')}
                  >
                    JSON
                  </Button>
                  <Button
                    variant={originalFormat === 'YAML' ? 'contained' : 'outlined'}
                    onClick={() => setValue('original_format', 'YAML')}
                  >
                    YAML
                  </Button>
                </ButtonGroup>
              </Box>
            </Box>
          </FormSection>
        </Paper>

        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">Contract Content</Typography>
            {showEditorTabs && (
              <Tabs value={editorTab} onChange={(_, v) => setEditorTab(v)}>
                <Tab label="Editor" value="editor" />
                <Tab label="Preview" value="preview" />
              </Tabs>
            )}
          </Box>
          <Divider sx={{ mb: 2 }} />

          {editorTab === 'editor' || !showEditorTabs ? (
            <Box>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Contract Content
                </Typography>
                <Textarea
                  value={originalRaw}
                  onChange={(value) => setValue('original_raw', value)}
                  rows={20}
                  placeholder={
                    originalFormat === 'JSON'
                      ? '{\n  "hub_contract_version": "1.0.0",\n  ...\n}'
                      : 'hub_contract_version: "1.0.0"\n...'
                  }
                  helperText={`Enter contract content in ${originalFormat} format`}
                  error={form.formState.errors.original_raw?.message}
                  style={{
                    fontFamily: 'monospace',
                    fontSize: '14px',
                  }}
                />
              </Box>

              <Box sx={{ mt: 2 }}>
                <FileUpload
                  accept={originalFormat === 'JSON' ? '.json' : '.yaml,.yml'}
                  maxSize={10 * 1024 * 1024} // 10MB
                  onUpload={handleFileUpload}
                />
              </Box>
            </Box>
          ) : (
            <Box>
              <CodeBlock
                code={formattedContract || 'No content to preview'}
                language={originalFormat.toLowerCase()}
                showCopy
              />
            </Box>
          )}
        </Paper>

        <FormActions
          form={form}
          submitLabel={submitLabel}
          resetLabel={cancelLabel}
          showReset={showCancel}
          loading={loading}
          onReset={handleCancel}
        />
      </form>
    </FormProvider>
  )
}

ContractForm.displayName = 'ContractForm'

