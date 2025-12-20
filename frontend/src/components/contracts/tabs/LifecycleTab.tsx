/**
 * LifecycleTab Component
 *
 * Tab for editing lifecycle policy (HubContract-specific):
 * - Data Source input
 * - Refresh Cadence selector
 * - SLAs (Availability, Latency P95)
 * - SLA visualization (charts/graphs)
 */

import React from 'react'
import {
  Box,
  TextField,
  Typography,
  Grid,
} from '@mui/material'
import { Select } from '@/components/forms/Select'
import type { HubContract, RefreshCadence } from '../types'

export interface LifecycleTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
}

/**
 * Refresh cadence options
 */
const REFRESH_CADENCE_OPTIONS: Array<{ value: RefreshCadence; label: string }> = [
  { value: 'REAL_TIME', label: 'Real Time' },
  { value: 'HOURLY', label: 'Hourly' },
  { value: 'DAILY', label: 'Daily' },
  { value: 'WEEKLY', label: 'Weekly' },
  { value: 'MONTHLY', label: 'Monthly' },
  { value: 'ON_DEMAND', label: 'On Demand' },
]

/**
 * LifecycleTab component
 */
export const LifecycleTab: React.FC<LifecycleTabProps> = ({ contract, onChange }) => {
  const lifecycle = contract.lifecycle || {}
  const slas = lifecycle.slas || {}

  const handleLifecycleChange = (field: string, value: any) => {
    onChange({
      ...contract,
      lifecycle: {
        ...lifecycle,
        [field]: value,
      },
    })
  }

  const handleSLAChange = (field: keyof typeof slas, value: number | undefined) => {
    onChange({
      ...contract,
      lifecycle: {
        ...lifecycle,
        slas: {
          ...slas,
          [field]: value,
        },
      },
    })
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Grid container spacing={3}>
        {/* Data Source */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Data Source"
            value={lifecycle.data_source || ''}
            onChange={(e) => handleLifecycleChange('data_source', e.target.value)}
            helperText="Source of the data (e.g., OLTP.orders, data-warehouse.customers)"
            placeholder="OLTP.orders"
          />
        </Grid>

        {/* Refresh Cadence */}
        <Grid item xs={12} sm={6}>
          <Select
            label="Refresh Cadence"
            value={lifecycle.refresh_cadence || ''}
            onChange={(value) => handleLifecycleChange('refresh_cadence', value)}
            options={REFRESH_CADENCE_OPTIONS}
            placeholder="Select refresh cadence"
          />
        </Grid>

        {/* SLAs Section */}
        <Grid item xs={12}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
            Service Level Agreements (SLAs)
          </Typography>
        </Grid>

        {/* Availability SLA */}
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Availability (%)"
            type="number"
            inputProps={{ min: 0, max: 100, step: 0.1 }}
            value={slas.availability ?? ''}
            onChange={(e) => {
              const value = e.target.value === '' ? undefined : parseFloat(e.target.value)
              handleSLAChange('availability', value)
            }}
            helperText="Target availability percentage (e.g., 99.0 for 99%)"
            placeholder="99.0"
          />
        </Grid>

        {/* Latency P95 SLA */}
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Latency P95 (ms)"
            type="number"
            inputProps={{ min: 0, step: 1 }}
            value={slas.latency_ms_p95 ?? ''}
            onChange={(e) => {
              const value = e.target.value === '' ? undefined : parseInt(e.target.value, 10)
              handleSLAChange('latency_ms_p95', value)
            }}
            helperText="95th percentile latency in milliseconds (e.g., 5000 for 5 seconds)"
            placeholder="5000"
          />
        </Grid>

        {/* SLA Visualization Placeholder */}
        {(slas.availability !== undefined || slas.latency_ms_p95 !== undefined) && (
          <Grid item xs={12}>
            <Box
              sx={{
                padding: 2,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                backgroundColor: 'background.default',
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                SLA Summary
              </Typography>
              <Box sx={{ display: 'flex', gap: 3 }}>
                {slas.availability !== undefined && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Availability
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {slas.availability}%
                    </Typography>
                  </Box>
                )}
                {slas.latency_ms_p95 !== undefined && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Latency P95
                    </Typography>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {slas.latency_ms_p95}ms
                    </Typography>
                  </Box>
                )}
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Note: Advanced SLA visualization with charts/graphs can be added as a future enhancement
              </Typography>
            </Box>
          </Grid>
        )}
      </Grid>
    </Box>
  )
}

LifecycleTab.displayName = 'LifecycleTab'

