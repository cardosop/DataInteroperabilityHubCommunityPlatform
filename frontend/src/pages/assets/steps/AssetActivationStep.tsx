/**
 * Asset Activation Step
 *
 * Final step: Review asset details and activate
 */

import React from 'react'
import { Box, Typography, Paper, Button, Alert } from '@mui/material'
import { CheckCircle as CheckCircleIcon, PlayArrow as PlayArrowIcon } from '@mui/icons-material'
import type { AssetFormData } from '../AssetFormPage'

export interface AssetActivationStepProps {
  formData: AssetFormData
  onUpdate: (updates: Partial<AssetFormData>) => void
}

/**
 * Asset Activation Step Component
 */
export const AssetActivationStep: React.FC<AssetActivationStepProps> = ({
  formData,
  onUpdate,
}) => {
  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Review & Activate
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Review your asset details before activation.
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Asset Name
            </Typography>
            <Typography variant="body1">{formData.name}</Typography>
          </Box>

          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Domain
            </Typography>
            <Typography variant="body1">{formData.domain || 'Not specified'}</Typography>
          </Box>

          <Box>
            <Typography variant="subtitle2" color="text.secondary">
              Onboarding Mode
            </Typography>
            <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
              {formData.onboardingMode.replace('-', ' ')}
            </Typography>
          </Box>

          {formData.contractId && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Contract
              </Typography>
              <Typography variant="body1">Contract ID: {formData.contractId}</Typography>
            </Box>
          )}

          {formData.datasetId && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                Dataset
              </Typography>
              <Typography variant="body1">Dataset ID: {formData.datasetId}</Typography>
            </Box>
          )}
        </Box>
      </Paper>

      <Alert severity="info" sx={{ mb: 3 }}>
        After activation, your asset will be available in the catalog. You can edit
        the contract and manage the asset from the asset detail page.
      </Alert>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button variant="outlined">Save as Draft</Button>
        <Button
          variant="contained"
          startIcon={<PlayArrowIcon />}
          onClick={() => {
            // Activation will be handled by the wizard completion
            onUpdate({})
          }}
        >
          Activate Asset
        </Button>
      </Box>
    </Box>
  )
}

