/**
 * Asset Metadata Step
 *
 * Step 1: Basic metadata and onboarding mode selection
 * Implements UI-DPO-001: Asset Creation (Step 1)
 */

import React from 'react'
import { Box, Grid, Typography, Paper } from '@mui/material'
import { TextInput } from '@/components/forms/TextInput'
import { Textarea } from '@/components/forms/Textarea'
import { Select } from '@/components/forms/Select'
import { TagInput } from '@/components/forms/TagInput'
import { RadioGroup } from '@/components/forms/RadioGroup'
import { FormSection } from '@/components/forms/FormSection'
import type { AssetFormData, OnboardingMode } from '../AssetFormPage'

export interface AssetMetadataStepProps {
  formData: AssetFormData
  onUpdate: (updates: Partial<AssetFormData>) => void
  onNameChange: (name: string) => void
  errors: Record<string, string>
}

/**
 * Common domains for assets
 */
const DOMAIN_OPTIONS = [
  { value: 'finance', label: 'Finance' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'sales', label: 'Sales' },
  { value: 'operations', label: 'Operations' },
  { value: 'hr', label: 'Human Resources' },
  { value: 'it', label: 'IT' },
  { value: 'analytics', label: 'Analytics' },
  { value: 'other', label: 'Other' },
]

/**
 * Onboarding mode options
 */
const ONBOARDING_MODE_OPTIONS = [
  {
    value: 'data-first',
    label: 'Data-First',
    description: 'Upload data first, then create contract from inferred schema',
  },
  {
    value: 'contract-first',
    label: 'Contract-First',
    description: 'Create contract first, then attach dataset',
  },
  {
    value: 'contract-only',
    label: 'Contract-Only',
    description: 'Create contract without dataset (for API-based assets)',
  },
]

/**
 * Asset Metadata Step Component
 */
export const AssetMetadataStep: React.FC<AssetMetadataStepProps> = ({
  formData,
  onUpdate,
  onNameChange,
  errors,
}) => {
  return (
    <Box>
      <Grid container spacing={4}>
        {/* Left Column: Basic Metadata */}
        <Grid item xs={12} md={6}>
          <FormSection title="Basic Information">
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <TextInput
                label="Asset Name"
                value={formData.name}
                onChange={onNameChange}
                error={errors.name}
                required
                placeholder="e.g., Customer Sales Data"
                helperText="A descriptive name for your asset"
              />

              <TextInput
                label="Asset Key"
                value={formData.key}
                onChange={(value) => onUpdate({ key: value })}
                error={errors.key}
                required
                placeholder="e.g., customer-sales-data"
                helperText="Unique identifier (auto-generated from name, lowercase with hyphens)"
              />

              <Textarea
                label="Description"
                value={formData.description}
                onChange={(value) => onUpdate({ description: value })}
                rows={4}
                placeholder="Describe what this asset contains and how it's used..."
                helperText="Optional: Provide a detailed description of the asset"
              />

              <Select
                label="Domain"
                options={DOMAIN_OPTIONS}
                value={formData.domain}
                onChange={(value) => onUpdate({ domain: value as string })}
                placeholder="Select a domain"
                helperText="Optional: Categorize the asset by business domain"
              />

              <TagInput
                label="Tags"
                value={formData.tags}
                onChange={(tags) => onUpdate({ tags })}
                placeholder="Add tags (press Enter)"
                helperText="Optional: Add tags to help organize and find assets"
              />
            </Box>
          </FormSection>
        </Grid>

        {/* Right Column: Onboarding Mode Selection */}
        <Grid item xs={12} md={6}>
          <FormSection title="Onboarding Mode">
            <Box sx={{ mb: 3 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Choose how you want to onboard this asset:
              </Typography>

              <RadioGroup
                options={ONBOARDING_MODE_OPTIONS.map((opt) => ({
                  value: opt.value,
                  label: opt.label,
                }))}
                value={formData.onboardingMode}
                onChange={(value) => onUpdate({ onboardingMode: value as OnboardingMode })}
                direction="vertical"
              />

              {/* Mode descriptions */}
              <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
                {ONBOARDING_MODE_OPTIONS.map((opt) => (
                  <Paper
                    key={opt.value}
                    sx={{
                      p: 2,
                      backgroundColor:
                        formData.onboardingMode === opt.value
                          ? 'primary.50'
                          : 'background.paper',
                      border: `1px solid ${
                        formData.onboardingMode === opt.value
                          ? 'primary.main'
                          : 'divider'
                      }`,
                    }}
                  >
                    <Typography variant="subtitle2" fontWeight={500}>
                      {opt.label}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {opt.description}
                    </Typography>
                  </Paper>
                ))}
              </Box>
            </Box>
          </FormSection>
        </Grid>
      </Grid>
    </Box>
  )
}

