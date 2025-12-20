/**
 * ComplianceTab Component
 *
 * Tab for editing compliance policy (HubContract-specific):
 * - Contains Personal Data checkbox
 * - Personal Data Categories multi-select
 * - Jurisdictions multi-select (GDPR, LGPD, CCPA, HIPAA, SOX)
 * - Legal Bases multi-select
 * - Retention Policy (period, notes)
 * - Compliance risk indicator
 */

import React from 'react'
import {
  Box,
  TextField,
  Typography,
  Grid,
  Checkbox,
  FormControlLabel,
} from '@mui/material'
import { MultiSelect } from '@/components/forms/MultiSelect'
import type {
  HubContract,
  ComplianceJurisdiction,
  LegalBasis,
  PersonalDataCategory,
} from '../types'

export interface ComplianceTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
}

/**
 * Personal data category options
 */
const PERSONAL_DATA_CATEGORIES: Array<{ value: PersonalDataCategory; label: string }> = [
  { value: 'EMAIL', label: 'Email' },
  { value: 'PHONE', label: 'Phone' },
  { value: 'NAME', label: 'Name' },
  { value: 'ADDRESS', label: 'Address' },
  { value: 'SSN', label: 'SSN' },
  { value: 'IP_ADDRESS', label: 'IP Address' },
  { value: 'LOCATION', label: 'Location' },
  { value: 'FINANCIAL', label: 'Financial' },
]

/**
 * Jurisdiction options
 */
const JURISDICTIONS: Array<{ value: ComplianceJurisdiction; label: string }> = [
  { value: 'GDPR', label: 'GDPR (EU)' },
  { value: 'LGPD', label: 'LGPD (Brazil)' },
  { value: 'CCPA', label: 'CCPA (California)' },
  { value: 'HIPAA', label: 'HIPAA (US Healthcare)' },
  { value: 'SOX', label: 'SOX (US Financial)' },
]

/**
 * Legal basis options
 */
const LEGAL_BASES: Array<{ value: LegalBasis; label: string }> = [
  { value: 'CONSENT', label: 'Consent' },
  { value: 'CONTRACT', label: 'Contract' },
  { value: 'LEGAL_OBLIGATION', label: 'Legal Obligation' },
  { value: 'VITAL_INTERESTS', label: 'Vital Interests' },
  { value: 'PUBLIC_TASK', label: 'Public Task' },
  { value: 'LEGITIMATE_INTERESTS', label: 'Legitimate Interests' },
]

/**
 * ComplianceTab component
 */
export const ComplianceTab: React.FC<ComplianceTabProps> = ({ contract, onChange }) => {
  const compliance = contract.privacy_compliance || {}

  const handleComplianceChange = (field: string, value: any) => {
    onChange({
      ...contract,
      privacy_compliance: {
        ...compliance,
        [field]: value,
      },
    })
  }

  const handleRetentionPolicyChange = (field: keyof typeof compliance.retention_policy, value: string) => {
    onChange({
      ...contract,
      privacy_compliance: {
        ...compliance,
        retention_policy: {
          ...compliance.retention_policy,
          [field]: value,
        },
      },
    })
  }

  // Calculate compliance risk
  const hasPersonalData = compliance.contains_personal_data || false
  const hasJurisdictions = (compliance.jurisdictions?.length || 0) > 0
  const hasLegalBases = (compliance.legal_bases?.length || 0) > 0
  const hasRetentionPolicy = !!compliance.retention_policy?.period

  const complianceRisk = hasPersonalData && (!hasJurisdictions || !hasLegalBases || !hasRetentionPolicy)
    ? 'high'
    : hasPersonalData && (!hasJurisdictions || !hasLegalBases)
    ? 'medium'
    : 'low'

  return (
    <Box sx={{ padding: 3 }}>
      <Grid container spacing={3}>
        {/* Contains Personal Data */}
        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                checked={hasPersonalData}
                onChange={(e) => handleComplianceChange('contains_personal_data', e.target.checked)}
              />
            }
            label="Contains Personal Data"
          />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
            Check this if the contract involves personal data that requires compliance measures
          </Typography>
        </Grid>

        {/* Personal Data Categories */}
        {hasPersonalData && (
          <Grid item xs={12}>
            <MultiSelect
              label="Personal Data Categories"
              value={compliance.personal_data_categories || []}
              onChange={(values) => handleComplianceChange('personal_data_categories', values)}
              options={PERSONAL_DATA_CATEGORIES}
              placeholder="Select personal data categories"
            />
          </Grid>
        )}

        {/* Jurisdictions */}
        {hasPersonalData && (
          <Grid item xs={12}>
            <MultiSelect
              label="Jurisdictions"
              value={compliance.jurisdictions || []}
              onChange={(values) => handleComplianceChange('jurisdictions', values)}
              options={JURISDICTIONS}
              placeholder="Select applicable jurisdictions"
            />
          </Grid>
        )}

        {/* Legal Bases */}
        {hasPersonalData && (
          <Grid item xs={12}>
            <MultiSelect
              label="Legal Bases"
              value={compliance.legal_bases || []}
              onChange={(values) => handleComplianceChange('legal_bases', values)}
              options={LEGAL_BASES}
              placeholder="Select legal bases for processing"
            />
          </Grid>
        )}

        {/* Retention Policy */}
        {hasPersonalData && (
          <>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Retention Period"
                value={compliance.retention_policy?.period || ''}
                onChange={(e) => handleRetentionPolicyChange('period', e.target.value)}
                helperText="ISO 8601 duration (e.g., P5Y for 5 years, P1Y for 1 year)"
                placeholder="P5Y"
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Retention Notes"
                multiline
                rows={3}
                value={compliance.retention_policy?.notes || ''}
                onChange={(e) => handleRetentionPolicyChange('notes', e.target.value)}
                helperText="Additional notes about the retention policy"
              />
            </Grid>
          </>
        )}

        {/* Compliance Risk Indicator */}
        {hasPersonalData && (
          <Grid item xs={12}>
            <Box
              sx={{
                padding: 2,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                backgroundColor:
                  complianceRisk === 'high'
                    ? 'error.light'
                    : complianceRisk === 'medium'
                    ? 'warning.light'
                    : 'success.light',
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                Compliance Risk: {complianceRisk.toUpperCase()}
              </Typography>
              <Typography variant="body2">
                {complianceRisk === 'high' &&
                  'High risk: Personal data is marked but jurisdictions, legal bases, or retention policy are missing.'}
                {complianceRisk === 'medium' &&
                  'Medium risk: Some compliance information is missing.'}
                {complianceRisk === 'low' &&
                  'Low risk: All required compliance information is provided.'}
              </Typography>
            </Box>
          </Grid>
        )}

        {!hasPersonalData && (
          <Grid item xs={12}>
            <Typography variant="body2" color="text.secondary">
              Enable "Contains Personal Data" to configure compliance settings.
            </Typography>
          </Grid>
        )}
      </Grid>
    </Box>
  )
}

ComplianceTab.displayName = 'ComplianceTab'

