/**
 * ViolationsList Component
 *
 * Component for displaying compliance violations with severity, description, and remediation.
 */

import React from 'react'
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material'
import type { ComplianceScanResults } from '@/lib/api/compliance'

export interface ViolationsListProps {
  violations?: ComplianceScanResults['violations']
  violationDetails?: ComplianceScanResults['violation_details']
  remediationSuggestions?: ComplianceScanResults['remediation_suggestions']
}

/**
 * Get violation severity color
 */
function getSeverityColor(severity?: string): 'error' | 'warning' | 'info' | 'default' {
  if (!severity) return 'default'
  const upperSeverity = severity.toUpperCase()
  if (upperSeverity.includes('CRITICAL') || upperSeverity.includes('HIGH')) return 'error'
  if (upperSeverity.includes('MEDIUM') || upperSeverity.includes('WARN')) return 'warning'
  return 'info'
}

/**
 * Get violation severity icon
 */
function getSeverityIcon(severity?: string) {
  if (!severity) return <InfoIcon />
  const upperSeverity = severity.toUpperCase()
  if (upperSeverity.includes('CRITICAL') || upperSeverity.includes('HIGH')) return <ErrorIcon />
  if (upperSeverity.includes('MEDIUM') || upperSeverity.includes('WARN')) return <WarningIcon />
  return <InfoIcon />
}

/**
 * ViolationsList component
 */
export const ViolationsList: React.FC<ViolationsListProps> = ({
  violations = [],
  violationDetails = [],
  remediationSuggestions = [],
}) => {
  if (violations.length === 0 && violationDetails.length === 0) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          No violations found
        </Typography>
      </Paper>
    )
  }

  // Group violations by severity
  const violationsBySeverity = React.useMemo(() => {
    const grouped: Record<string, typeof violations> = {
      CRITICAL: [],
      HIGH: [],
      MEDIUM: [],
      LOW: [],
      INFO: [],
      OTHER: [],
    }

    violations.forEach((violation) => {
      const severity = violation.severity?.toUpperCase() || 'OTHER'
      if (severity.includes('CRITICAL')) {
        grouped.CRITICAL.push(violation)
      } else if (severity.includes('HIGH')) {
        grouped.HIGH.push(violation)
      } else if (severity.includes('MEDIUM')) {
        grouped.MEDIUM.push(violation)
      } else if (severity.includes('LOW')) {
        grouped.LOW.push(violation)
      } else if (severity.includes('INFO')) {
        grouped.INFO.push(violation)
      } else {
        grouped.OTHER.push(violation)
      }
    })

    return grouped
  }, [violations])

  return (
    <Box>
      {/* Violations by Severity */}
      {Object.entries(violationsBySeverity).map(([severity, severityViolations]) => {
        if (severityViolations.length === 0) return null

        return (
          <Accordion key={severity} defaultExpanded={severity === 'CRITICAL' || severity === 'HIGH'}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                {getSeverityIcon(severity)}
                <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                  {severity} ({severityViolations.length})
                </Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Type</TableCell>
                      <TableCell>Description</TableCell>
                      <TableCell>Remediation</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {severityViolations.map((violation, index) => (
                      <TableRow key={violation.id || index}>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Chip
                              label={violation.type || 'Unknown'}
                              size="small"
                              color={getSeverityColor(violation.severity)}
                            />
                            {violation.severity && (
                              <Chip
                                label={violation.severity}
                                size="small"
                                color={getSeverityColor(violation.severity)}
                                variant="outlined"
                              />
                            )}
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">{violation.description || '—'}</Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">
                            {violation.remediation || '—'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </AccordionDetails>
          </Accordion>
        )
      })}

      {/* Remediation Suggestions */}
      {remediationSuggestions && remediationSuggestions.length > 0 && (
        <Paper sx={{ p: 2, mt: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Remediation Suggestions
          </Typography>
          <Box component="ul" sx={{ pl: 3, m: 0 }}>
            {remediationSuggestions.map((suggestion, index) => (
              <li key={index}>
                <Typography variant="body2">
                  {typeof suggestion === 'string' ? suggestion : JSON.stringify(suggestion)}
                </Typography>
              </li>
            ))}
          </Box>
        </Paper>
      )}
    </Box>
  )
}

ViolationsList.displayName = 'ViolationsList'

