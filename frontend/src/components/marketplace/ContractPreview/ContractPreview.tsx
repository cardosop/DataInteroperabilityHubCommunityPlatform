/**
 * ContractPreview Component for Marketplace
 *
 * Simplified preview component for marketplace contracts.
 * Shows key contract information in a compact, readable format.
 * Used in marketplace listings and modals.
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
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
  Description as DescriptionIcon,
  Schema as SchemaIcon,
  Security as SecurityIcon,
  Speed as SpeedIcon,
  Store as StoreIcon,
} from '@mui/icons-material'
import type { HubContract } from '@/components/contracts/types'

export interface ContractPreviewProps {
  /**
   * HubContract to preview
   */
  contract: HubContract
  /**
   * Show full details or compact view
   * @default false
   */
  compact?: boolean
  /**
   * Show all sections or only key sections
   * @default false
   */
  showAllSections?: boolean
}

/**
 * ContractPreview Component for Marketplace
 *
 * @example
 * ```tsx
 * <ContractPreview
 *   contract={hubContract}
 *   compact={false}
 *   showAllSections={true}
 * />
 * ```
 */
export const ContractPreview: React.FC<ContractPreviewProps> = ({
  contract,
  compact = false,
  showAllSections = false,
}) => {
  const contractName = contract.info.name || 'Unnamed Contract'
  const contractDescription = contract.info.description
  const contractVersion = contract.info.version
  const contractDomain = contract.info.domain
  const contractTags = contract.info.tags || []
  const contractOwners = contract.info.owners || []

  if (compact) {
    return (
      <Box>
        {/* Header */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
            {contractName}
          </Typography>
          {contractDescription && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {contractDescription}
            </Typography>
          )}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
            {contractDomain && <Chip label={contractDomain} size="small" />}
            {contractTags.slice(0, 3).map((tag, index) => (
              <Chip key={index} label={tag} size="small" variant="outlined" />
            ))}
            {contractTags.length > 3 && (
              <Chip label={`+${contractTags.length - 3}`} size="small" variant="outlined" />
            )}
          </Box>
        </Box>

        {/* Schema Summary */}
        {contract.schema?.fields && contract.schema.fields.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
              Schema: {contract.schema.fields.length} fields
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {contract.schema.fields.slice(0, 5).map((f) => f.name).join(', ')}
              {contract.schema.fields.length > 5 && '...'}
            </Typography>
          </Box>
        )}
      </Box>
    )
  }

  return (
    <Box>
      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>
          {contractName}
        </Typography>
        {contractVersion && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Version: {contractVersion}
          </Typography>
        )}
        {contractDescription && (
          <Typography variant="body1" sx={{ mb: 2, whiteSpace: 'pre-wrap' }}>
            {contractDescription}
          </Typography>
        )}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {contractDomain && <Chip label={`Domain: ${contractDomain}`} size="small" />}
          {contractTags.map((tag, index) => (
            <Chip key={index} label={tag} size="small" variant="outlined" />
          ))}
        </Box>
      </Paper>

      {/* Owners */}
      {contractOwners.length > 0 && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <DescriptionIcon fontSize="small" />
            Owners
          </Typography>
          <Grid container spacing={2}>
            {contractOwners.map((owner, index) => (
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
        <Accordion defaultExpanded={showAllSections}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
              <SchemaIcon fontSize="small" />
              Schema Fields ({contract.schema.fields.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Field Name</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Data Type</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Nullable</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Description</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {contract.schema.fields.slice(0, showAllSections ? undefined : 10).map((field, index) => (
                    <TableRow key={index}>
                      <TableCell sx={{ fontWeight: 500 }}>{field.name}</TableCell>
                      <TableCell>
                        <Chip label={field.data_type} size="small" />
                      </TableCell>
                      <TableCell>{field.nullable ? 'Yes' : 'No'}</TableCell>
                      <TableCell>{field.description || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            {!showAllSections && contract.schema.fields.length > 10 && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>
                Showing 10 of {contract.schema.fields.length} fields
              </Typography>
            )}
          </AccordionDetails>
        </Accordion>
      )}

      {/* Quality Rules */}
      {contract.quality?.rules && contract.quality.rules.length > 0 && showAllSections && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
              <SpeedIcon fontSize="small" />
              Quality Rules ({contract.quality.rules.length})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Dimension</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>Severity</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {contract.quality.rules.map((rule, index) => (
                    <TableRow key={index}>
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
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      )}

      {/* Compliance */}
      {contract.privacy_compliance && showAllSections && (
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
              <SecurityIcon fontSize="small" />
              Privacy & Compliance
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
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
                      Categories:
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {contract.privacy_compliance.personal_data_categories.map((category, index) => (
                        <Chip key={index} label={category} size="small" />
                      ))}
                    </Box>
                  </Grid>
                )}
            </Grid>
          </AccordionDetails>
        </Accordion>
      )}

      {/* Marketplace Policy */}
      {contract.marketplace && (
        <Accordion defaultExpanded={!showAllSections}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
              <StoreIcon fontSize="small" />
              Marketplace Policy
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
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
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  )
}

ContractPreview.displayName = 'ContractPreview'

