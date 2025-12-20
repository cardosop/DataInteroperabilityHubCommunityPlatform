/**
 * ViolationScanSection Component
 *
 * Component for displaying violations for a specific compliance scan.
 * Fetches scan results and displays violations.
 */

import React from 'react'
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Alert,
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material'
import { useComplianceScanResults } from '@/hooks/useComplianceScanResults'
import { ViolationsList } from './ViolationsList'
import type { ComplianceScan } from '@/lib/api/compliance'

export interface ViolationScanSectionProps {
  scan: ComplianceScan
}

/**
 * ViolationScanSection component
 */
export const ViolationScanSection: React.FC<ViolationScanSectionProps> = ({ scan }) => {
  const { data: results, isLoading, error } = useComplianceScanResults(
    scan.id,
    { enabled: scan.status === 'SUCCEEDED' }
  )

  const hasViolations = results?.violations && results.violations.length > 0

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', pr: 2 }}>
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Scan {scan.id.substring(0, 8)}...
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {scan.completed_at
                ? `Completed ${new Date(scan.completed_at).toLocaleDateString()}`
                : 'In progress'}
            </Typography>
          </Box>
          {results && (
            <Typography variant="body2" color="text.secondary">
              {results.violations?.length || 0} violation{results.violations?.length !== 1 ? 's' : ''}
            </Typography>
          )}
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        {isLoading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}
        {error && (
          <Alert severity="warning">
            Could not load violation details: {error.message}
          </Alert>
        )}
        {results && (
          <Box>
            {hasViolations ? (
              <ViolationsList
                violations={results.violations}
                violationDetails={results.violation_details}
                remediationSuggestions={results.remediation_suggestions}
              />
            ) : (
              <Alert severity="success">No violations found in this scan.</Alert>
            )}
          </Box>
        )}
        {scan.status !== 'SUCCEEDED' && (
          <Alert severity="info">
            Scan is {scan.status.toLowerCase()}. Violations will be available once the scan completes.
          </Alert>
        )}
      </AccordionDetails>
    </Accordion>
  )
}

ViolationScanSection.displayName = 'ViolationScanSection'

