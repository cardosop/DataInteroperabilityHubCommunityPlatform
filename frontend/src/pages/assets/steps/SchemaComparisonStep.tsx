/**
 * Schema Comparison Step
 *
 * Step for contract-first flow: Compare inferred schema with contract schema
 */

import React from 'react'
import { Box, Typography, Paper, Alert, Button } from '@mui/material'
import { CompareArrows as CompareArrowsIcon } from '@mui/icons-material'
import type { AssetFormData } from '../AssetFormPage'

export interface SchemaComparisonStepProps {
  formData: AssetFormData
  onUpdate: (updates: Partial<AssetFormData>) => void
}

/**
 * Schema Comparison Step Component
 */
export const SchemaComparisonStep: React.FC<SchemaComparisonStepProps> = ({
  formData,
  onUpdate,
}) => {
  // This step would fetch and compare schemas
  // For now, we show a placeholder

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Schema Comparison
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Compare the inferred schema from your dataset with the contract schema.
      </Typography>

      <Paper sx={{ p: 3 }}>
        <Alert severity="info" sx={{ mb: 3 }}>
          Schema comparison will be displayed here once the dataset is analyzed.
          This step is optional and can be skipped.
        </Alert>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
          <Button
            variant="outlined"
            onClick={() => {
              // Skip this step
              onUpdate({})
            }}
          >
            Skip Comparison
          </Button>
          <Button
            variant="contained"
            startIcon={<CompareArrowsIcon />}
            onClick={() => {
              // Proceed with comparison
              onUpdate({})
            }}
          >
            Compare Schemas
          </Button>
        </Box>
      </Paper>
    </Box>
  )
}

