/**
 * Asset Form Component
 *
 * Form component for creating and editing assets.
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
} from '@mui/material'
import type { Asset, CreateAssetRequest, UpdateAssetRequest } from '@/lib/api/assets'
import { FormField } from '@/components/forms/FormField'
import { FormSection } from '@/components/forms/FormSection'
import { FormActions } from '@/components/forms/FormActions'
import type { UseFormReturn } from 'react-hook-form'

// Validation schema
const assetFormSchema = z.object({
  key: z
    .string()
    .min(1, 'Key is required')
    .max(255, 'Key must be 255 characters or less')
    .regex(/^[a-z0-9-_]+$/, 'Key must contain only lowercase letters, numbers, hyphens, and underscores'),
  name: z
    .string()
    .min(1, 'Name is required')
    .max(255, 'Name must be 255 characters or less'),
  description: z
    .string()
    .max(5000, 'Description must be 5000 characters or less')
    .nullable()
    .optional(),
  domain: z
    .string()
    .max(100, 'Domain must be 100 characters or less')
    .nullable()
    .optional(),
  visibility: z.enum(['INTERNAL', 'PUBLIC']).optional(),
  status: z.enum(['DRAFT', 'ACTIVE', 'PUBLIC', 'RETIRED']).optional(),
  version: z.number().optional(),
})

export type AssetFormData = z.infer<typeof assetFormSchema>

export interface AssetFormProps {
  /**
   * Existing asset data (for edit mode)
   */
  asset?: Asset
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
  onSubmit: (data: CreateAssetRequest | UpdateAssetRequest) => void | Promise<void>
  /**
   * Callback when form is cancelled
   */
  onCancel?: () => void
  /**
   * Form mode
   * @default 'create'
   */
  mode?: 'create' | 'edit'
}

/**
 * Asset Form Component
 *
 * @example
 * ```tsx
 * <AssetForm
 *   asset={asset}
 *   mode="edit"
 *   onSubmit={async (data) => {
 *     await updateAsset.mutateAsync({ id: asset.id, ...data, version: asset.version })
 *   }}
 *   onCancel={() => navigate('/assets')}
 * />
 * ```
 */
export const AssetForm: React.FC<AssetFormProps> = ({
  asset,
  loading = false,
  submitLabel = 'Save',
  showCancel = true,
  cancelLabel = 'Cancel',
  onSubmit,
  onCancel,
  mode = 'create',
}) => {
  const form = useForm<AssetFormData>({
    resolver: zodResolver(assetFormSchema),
    defaultValues: {
      key: asset?.key || '',
      name: asset?.name || '',
      description: asset?.description || null,
      domain: asset?.domain || null,
      visibility: asset?.visibility || 'INTERNAL',
      status: asset?.status || 'DRAFT',
      version: asset?.version,
    },
    mode: 'onBlur',
  })

  const { handleSubmit, reset } = form

  // Reset form when asset changes
  useEffect(() => {
    if (asset) {
      reset({
        key: asset.key,
        name: asset.name,
        description: asset.description || null,
        domain: asset.domain || null,
        visibility: asset.visibility,
        status: asset.status,
        version: asset.version,
      })
    }
  }, [asset, reset])

  const handleFormSubmit = async (data: AssetFormData) => {
    if (mode === 'edit' && asset) {
      const updateData: UpdateAssetRequest = {
        name: data.name,
        description: data.description,
        domain: data.domain,
        status: data.status,
        visibility: data.visibility,
        version: asset.version, // Include current version for optimistic locking
      }
      await onSubmit(updateData)
    } else {
      const createData: CreateAssetRequest = {
        key: data.key!,
        name: data.name!,
        description: data.description || null,
        domain: data.domain || null,
        visibility: data.visibility || 'INTERNAL',
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

  return (
    <FormProvider {...form}>
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            {mode === 'edit' ? 'Edit Asset' : 'Create Asset'}
          </Typography>
          <Divider sx={{ my: 2 }} />

          <FormSection title="Basic Information">
            {mode === 'create' && (
              <FormField
                name="key"
                label="Key"
                type="text"
                required
                helperText="Unique identifier for the asset (lowercase letters, numbers, hyphens, and underscores only)"
              />
            )}
            {mode === 'edit' && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Key
                </Typography>
                <Typography variant="body1">{asset?.key}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Key cannot be changed after creation
                </Typography>
              </Box>
            )}

            <FormField
              name="name"
              label="Name"
              type="text"
              required
              helperText="Display name for the asset"
            />

            <FormField
              name="description"
              label="Description"
              type="textarea"
              multiline
              rows={4}
              helperText="Detailed description of the asset (optional)"
            />

            <FormField
              name="domain"
              label="Domain"
              type="text"
              helperText="Domain or category for the asset (e.g., marketing, finance) (optional)"
            />
          </FormSection>

          <FormSection title="Settings">
            <FormField
              name="visibility"
              label="Visibility"
              type="select"
              options={[
                { value: 'INTERNAL', label: 'Internal' },
                { value: 'PUBLIC', label: 'Public' },
              ]}
              helperText="Who can see this asset"
            />

            {mode === 'edit' && (
              <FormField
                name="status"
                label="Status"
                type="select"
                options={[
                  { value: 'DRAFT', label: 'Draft' },
                  { value: 'ACTIVE', label: 'Active' },
                  { value: 'PUBLIC', label: 'Public' },
                  { value: 'RETIRED', label: 'Retired' },
                ]}
                helperText="Current status of the asset"
              />
            )}
          </FormSection>

          <Box sx={{ mt: 3 }}>
            <FormActions
              form={form}
              submitLabel={submitLabel}
              resetLabel={cancelLabel}
              showReset={showCancel}
              showClear={false}
              loading={loading}
              align="right"
              onSubmit={handleFormSubmit}
              onReset={handleCancel}
            />
          </Box>
        </Paper>
      </form>
    </FormProvider>
  )
}

AssetForm.displayName = 'AssetForm'

