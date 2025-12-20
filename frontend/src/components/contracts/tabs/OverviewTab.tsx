/**
 * OverviewTab Component
 *
 * Tab for editing contract overview information:
 * - Name, Description, Version fields
 * - Owners array (add/remove, name/email)
 * - Tags input (multi-select with autocomplete)
 * - Domain selector
 */

import React, { useState } from 'react'
import {
  Box,
  TextField,
  Button,
  IconButton,
  Typography,
  Grid,
} from '@mui/material'
import {
  Add as AddIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material'
import { TagInput } from '@/components/forms/TagInput'
import { Select } from '@/components/forms/Select'
import type { HubContract, Owner } from '../types'

export interface OverviewTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
  tagSuggestions?: string[]
  domainOptions?: string[]
}

/**
 * Common domain options
 */
const DEFAULT_DOMAIN_OPTIONS = [
  'analytics',
  'customer',
  'product',
  'sales',
  'marketing',
  'finance',
  'operations',
  'hr',
  'engineering',
  'data',
]

/**
 * OverviewTab component
 */
export const OverviewTab: React.FC<OverviewTabProps> = ({
  contract,
  onChange,
  tagSuggestions = [],
  domainOptions = DEFAULT_DOMAIN_OPTIONS,
}) => {
  const handleInfoChange = (field: keyof HubContract['info'], value: any) => {
    onChange({
      ...contract,
      info: {
        ...contract.info,
        [field]: value,
      },
    })
  }

  const handleOwnerAdd = () => {
    const newOwners = [...(contract.info.owners || []), { name: '', email: '' }]
    handleInfoChange('owners', newOwners)
  }

  const handleOwnerRemove = (index: number) => {
    const newOwners = contract.info.owners?.filter((_, i) => i !== index) || []
    handleInfoChange('owners', newOwners)
  }

  const handleOwnerChange = (index: number, field: keyof Owner, value: string) => {
    const newOwners = [...(contract.info.owners || [])]
    newOwners[index] = {
      ...newOwners[index],
      [field]: value,
    }
    handleInfoChange('owners', newOwners)
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Grid container spacing={3}>
        {/* Name */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Contract Name"
            required
            value={contract.info.name || ''}
            onChange={(e) => handleInfoChange('name', e.target.value)}
            helperText="A descriptive name for this contract"
          />
        </Grid>

        {/* Description */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Description"
            multiline
            rows={4}
            value={contract.info.description || ''}
            onChange={(e) => handleInfoChange('description', e.target.value)}
            helperText="A detailed description of what this contract represents"
          />
        </Grid>

        {/* Version */}
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Version"
            value={contract.info.version || ''}
            onChange={(e) => handleInfoChange('version', e.target.value)}
            helperText="Contract version (e.g., 1.0.0)"
          />
        </Grid>

        {/* Domain */}
        <Grid item xs={12} sm={6}>
          <Select
            label="Domain"
            value={contract.info.domain || ''}
            onChange={(value) => handleInfoChange('domain', value)}
            options={domainOptions.map((domain) => ({
              value: domain,
              label: domain.charAt(0).toUpperCase() + domain.slice(1),
            }))}
            placeholder="Select a domain"
          />
        </Grid>

        {/* Owners */}
        <Grid item xs={12}>
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                Owners
              </Typography>
              <Button
                size="small"
                startIcon={<AddIcon />}
                onClick={handleOwnerAdd}
              >
                Add Owner
              </Button>
            </Box>
            {contract.info.owners && contract.info.owners.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {contract.info.owners.map((owner, index) => (
                  <Box
                    key={index}
                    sx={{
                      display: 'flex',
                      gap: 2,
                      alignItems: 'flex-start',
                      padding: 2,
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1,
                    }}
                  >
                    <TextField
                      label="Name"
                      value={owner.name}
                      onChange={(e) => handleOwnerChange(index, 'name', e.target.value)}
                      sx={{ flex: 1 }}
                    />
                    <TextField
                      label="Email"
                      type="email"
                      value={owner.email}
                      onChange={(e) => handleOwnerChange(index, 'email', e.target.value)}
                      sx={{ flex: 1 }}
                    />
                    <IconButton
                      color="error"
                      onClick={() => handleOwnerRemove(index)}
                      sx={{ mt: 1 }}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No owners added. Click "Add Owner" to add one.
              </Typography>
            )}
          </Box>
        </Grid>

        {/* Tags */}
        <Grid item xs={12}>
          <TagInput
            label="Tags"
            value={contract.info.tags || []}
            onChange={(tags) => handleInfoChange('tags', tags)}
            suggestions={tagSuggestions}
            placeholder="Add tags (press Enter or comma to add)"
          />
        </Grid>
      </Grid>
    </Box>
  )
}

OverviewTab.displayName = 'OverviewTab'

