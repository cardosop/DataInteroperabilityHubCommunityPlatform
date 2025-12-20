/**
 * ContractPreview Component
 *
 * Read-only preview of the contract showing all sections in a formatted view.
 * Displays contract information in a clean, readable format without editing capabilities.
 */

import React from 'react'
import {
  Box,
  Typography,
  Paper,
  Grid,
  Chip,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import { Badge } from '@/components/data-display/Badge'
import type { HubContract } from './types'

export interface ContractPreviewProps {
  contract: HubContract
}

/**
 * ContractPreview component
 */
export const ContractPreview: React.FC<ContractPreviewProps> = ({ contract }) => {
  return (
    <Box sx={{ padding: 3, maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
          {contract.info.name || 'Unnamed Contract'}
        </Typography>
        {contract.info.version && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Version: {contract.info.version}
          </Typography>
        )}
        {contract.info.description && (
          <Typography variant="body1" sx={{ mb: 2 }}>
            {contract.info.description}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {contract.info.domain && (
            <Chip label={`Domain: ${contract.info.domain}`} size="small" />
          )}
          {contract.info.tags && contract.info.tags.length > 0 && (
            <>
              {contract.info.tags.map((tag, index) => (
                <Chip key={index} label={tag} size="small" variant="outlined" />
              ))}
            </>
          )}
        </Box>
      </Paper>

      {/* Owners */}
      {contract.info.owners && contract.info.owners.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Owners
          </Typography>
          <Grid container spacing={2}>
            {contract.info.owners.map((owner, index) => (
              <Grid item xs={12} sm={6} key={index}>
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {owner.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {owner.email}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {/* Schema */}
      {contract.schema?.fields && contract.schema.fields.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Schema Fields ({contract.schema.fields.length})
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Field Name</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Data Type</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Nullable</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Constraints</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {contract.schema.fields.map((field, index) => (
                  <TableRow key={index}>
                    <TableCell sx={{ fontWeight: 500 }}>{field.name}</TableCell>
                    <TableCell>
                      <Chip label={field.data_type} size="small" />
                    </TableCell>
                    <TableCell>{field.nullable ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{field.description || '—'}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {contract.schema?.primary_key?.includes(field.name) && (
                          <Chip label="PK" size="small" color="primary" />
                        )}
                        {field.is_unique && (
                          <Chip label="Unique" size="small" variant="outlined" />
                        )}
                        {field.is_indexed && (
                          <Chip label="Indexed" size="small" variant="outlined" />
                        )}
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Quality Rules */}
      {contract.quality?.rules && contract.quality.rules.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Quality Rules ({contract.quality.rules.length})
          </Typography>
          {contract.quality.default_profile_key && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Default Profile: {contract.quality.default_profile_key}
            </Typography>
          )}
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Rule ID</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Dimension</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Severity</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Target</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {contract.quality.rules.map((rule, index) => (
                  <TableRow key={index}>
                    <TableCell>{rule.rule_id}</TableCell>
                    <TableCell>{rule.name}</TableCell>
                    <TableCell>
                      <Chip label={rule.dimension} size="small" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={rule.severity}
                        size="small"
                        color={
                          rule.severity === 'ERROR'
                            ? 'error'
                            : rule.severity === 'WARNING'
                            ? 'warning'
                            : 'default'
                        }
                      />
                    </TableCell>
                    <TableCell>
                      {rule.target_level && (
                        <Typography variant="body2">
                          {rule.target_level}
                          {rule.target_column && `: ${rule.target_column}`}
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Compliance */}
      {contract.privacy_compliance && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Privacy & Compliance
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                Contains Personal Data:{' '}
                {contract.privacy_compliance.contains_personal_data ? 'Yes' : 'No'}
              </Typography>
            </Grid>
            {contract.privacy_compliance.personal_data_categories &&
              contract.privacy_compliance.personal_data_categories.length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                    Personal Data Categories:
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {contract.privacy_compliance.personal_data_categories.map((category, index) => (
                      <Chip key={index} label={category} size="small" />
                    ))}
                  </Box>
                </Grid>
              )}
            {contract.privacy_compliance.jurisdictions &&
              contract.privacy_compliance.jurisdictions.length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                    Jurisdictions:
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {contract.privacy_compliance.jurisdictions.map((jurisdiction, index) => (
                      <Chip key={index} label={jurisdiction} size="small" color="primary" />
                    ))}
                  </Box>
                </Grid>
              )}
            {contract.privacy_compliance.legal_bases &&
              contract.privacy_compliance.legal_bases.length > 0 && (
                <Grid item xs={12}>
                  <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                    Legal Bases:
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {contract.privacy_compliance.legal_bases.map((basis, index) => (
                      <Chip key={index} label={basis} size="small" variant="outlined" />
                    ))}
                  </Box>
                </Grid>
              )}
            {contract.privacy_compliance.retention_policy && (
              <Grid item xs={12}>
                <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                  Retention Policy:
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Period: {contract.privacy_compliance.retention_policy.period || 'Not specified'}
                </Typography>
                {contract.privacy_compliance.retention_policy.notes && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    {contract.privacy_compliance.retention_policy.notes}
                  </Typography>
                )}
              </Grid>
            )}
          </Grid>
        </Paper>
      )}

      {/* Lifecycle */}
      {contract.lifecycle && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Lifecycle Policy
          </Typography>
          <Grid container spacing={2}>
            {contract.lifecycle.data_source && (
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                  Data Source
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {contract.lifecycle.data_source}
                </Typography>
              </Grid>
            )}
            {contract.lifecycle.refresh_cadence && (
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                  Refresh Cadence
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {contract.lifecycle.refresh_cadence}
                </Typography>
              </Grid>
            )}
            {contract.lifecycle.slas && (
              <Grid item xs={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                  Service Level Agreements
                </Typography>
                <Grid container spacing={2}>
                  {contract.lifecycle.slas.availability !== undefined && (
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                        Availability
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {contract.lifecycle.slas.availability}%
                      </Typography>
                    </Grid>
                  )}
                  {contract.lifecycle.slas.latency_ms_p95 !== undefined && (
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                        Latency P95
                      </Typography>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {contract.lifecycle.slas.latency_ms_p95}ms
                      </Typography>
                    </Grid>
                  )}
                </Grid>
              </Grid>
            )}
          </Grid>
        </Paper>
      )}

      {/* Marketplace */}
      {contract.marketplace && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Marketplace Policy
          </Typography>
          {contract.marketplace.license_summary && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                License Summary
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                {contract.marketplace.license_summary}
              </Typography>
            </Box>
          )}
          {contract.marketplace.intended_use && contract.marketplace.intended_use.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                Intended Use
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {contract.marketplace.intended_use.map((use, index) => (
                  <Chip key={index} label={use} size="small" color="success" />
                ))}
              </Box>
            </Box>
          )}
          {contract.marketplace.restricted_use && contract.marketplace.restricted_use.length > 0 && (
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 500, mb: 1 }}>
                Restricted Use
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {contract.marketplace.restricted_use.map((use, index) => (
                  <Chip key={index} label={use} size="small" color="error" />
                ))}
              </Box>
            </Box>
          )}
        </Paper>
      )}

      {/* Contract Metadata */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Contract Metadata
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
              Contract ID
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
              {contract.id}
            </Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
              Hub Contract Version
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {contract.hub_contract_version}
            </Typography>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  )
}

ContractPreview.displayName = 'ContractPreview'

