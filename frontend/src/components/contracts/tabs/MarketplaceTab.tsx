/**
 * MarketplaceTab Component
 *
 * Tab for editing marketplace policy (HubContract-specific):
 * - License Summary input
 * - Intended Use multi-select
 * - Restricted Use multi-select
 */

import React from 'react'
import {
  Box,
  TextField,
  Typography,
  Grid,
} from '@mui/material'
import { MultiSelect } from '@/components/forms/MultiSelect'
import type { HubContract, IntendedUse, RestrictedUse } from '../types'

export interface MarketplaceTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
}

/**
 * Intended use options
 */
const INTENDED_USE_OPTIONS: Array<{ value: IntendedUse; label: string }> = [
  { value: 'analytics', label: 'Analytics' },
  { value: 'machine_learning', label: 'Machine Learning' },
  { value: 'reporting', label: 'Reporting' },
  { value: 'data_integration', label: 'Data Integration' },
  { value: 'compliance', label: 'Compliance' },
]

/**
 * Restricted use options
 */
const RESTRICTED_USE_OPTIONS: Array<{ value: RestrictedUse; label: string }> = [
  { value: 'resale', label: 'Resale' },
  { value: 'competitive_analysis', label: 'Competitive Analysis' },
  { value: 'marketing', label: 'Marketing' },
  { value: 'third_party_sharing', label: 'Third Party Sharing' },
]

/**
 * MarketplaceTab component
 */
export const MarketplaceTab: React.FC<MarketplaceTabProps> = ({ contract, onChange }) => {
  const marketplace = contract.marketplace || {}

  const handleMarketplaceChange = (field: string, value: any) => {
    onChange({
      ...contract,
      marketplace: {
        ...marketplace,
        [field]: value,
      },
    })
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Grid container spacing={3}>
        {/* License Summary */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="License Summary"
            multiline
            rows={4}
            value={marketplace.license_summary || ''}
            onChange={(e) => handleMarketplaceChange('license_summary', e.target.value)}
            helperText="Summary of the license terms for this data contract"
            placeholder="This data contract is licensed under..."
          />
        </Grid>

        {/* Intended Use */}
        <Grid item xs={12}>
          <MultiSelect
            label="Intended Use"
            value={marketplace.intended_use || []}
            onChange={(values) => handleMarketplaceChange('intended_use', values)}
            options={INTENDED_USE_OPTIONS}
            placeholder="Select intended use cases"
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            Select the primary use cases for this data contract
          </Typography>
        </Grid>

        {/* Restricted Use */}
        <Grid item xs={12}>
          <MultiSelect
            label="Restricted Use"
            value={marketplace.restricted_use || []}
            onChange={(values) => handleMarketplaceChange('restricted_use', values)}
            options={RESTRICTED_USE_OPTIONS}
            placeholder="Select restricted use cases"
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            Select use cases that are explicitly restricted for this data contract
          </Typography>
        </Grid>
      </Grid>
    </Box>
  )
}

MarketplaceTab.displayName = 'MarketplaceTab'

