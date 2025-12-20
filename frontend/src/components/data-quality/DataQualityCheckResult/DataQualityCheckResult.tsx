/**
 * DataQualityCheckResult Component
 *
 * Reusable component for displaying individual data quality check results.
 * Shows check name, type, status, message, and expandable details.
 */

import React, { useState } from 'react'
import {
  Box,
  Typography,
  Paper,
  Chip,
  IconButton,
  Collapse,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
} from '@mui/icons-material'
import type { DQRunResults } from '@/lib/api/data-quality'

export interface DataQualityCheckResultProps {
  /**
   * Check result data
   */
  check: DQRunResults['checks'][0]
  /**
   * Show expandable details
   * @default true
   */
  showDetails?: boolean
  /**
   * Initially expanded
   * @default false
   */
  defaultExpanded?: boolean
}

/**
 * Get check status icon
 */
function getStatusIcon(status: string) {
  switch (status) {
    case 'PASS':
      return <CheckCircleIcon color="success" />
    case 'WARN':
      return <WarningIcon color="warning" />
    case 'FAIL':
      return <ErrorIcon color="error" />
    default:
      return <HelpIcon color="action" />
  }
}

/**
 * Get check status color
 */
function getStatusColor(status: string): 'success' | 'warning' | 'error' | 'default' {
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    default:
      return 'default'
  }
}

/**
 * DataQualityCheckResult Component
 *
 * @example
 * ```tsx
 * <DataQualityCheckResult check={checkResult} />
 * ```
 */
export const DataQualityCheckResult: React.FC<DataQualityCheckResultProps> = ({
  check,
  showDetails = true,
  defaultExpanded = false,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded)

  const handleToggleExpand = () => {
    setExpanded(!expanded)
  }

  return (
    <Paper sx={{ p: 2, mb: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box sx={{ flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            {getStatusIcon(check.status)}
            <Typography variant="h6">{check.name}</Typography>
            <Chip
              label={check.status}
              size="small"
              color={getStatusColor(check.status)}
            />
            {check.type && (
              <Chip
                label={check.type}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
          {check.message && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {check.message}
            </Typography>
          )}
          {check.expectation && (
            <Typography variant="body2" color="text.secondary">
              <strong>Expectation:</strong> {check.expectation}
            </Typography>
          )}
        </Box>
        {showDetails && (
          <IconButton onClick={handleToggleExpand} size="small">
            {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </IconButton>
        )}
      </Box>

      {/* Expandable Details */}
      {showDetails && (
        <Collapse in={expanded}>
          <Box sx={{ mt: 2 }}>
            {check.result && Object.keys(check.result).length > 0 && (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Property</TableCell>
                      <TableCell>Value</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(check.result).map(([key, value]) => (
                      <TableRow key={key}>
                        <TableCell>
                          <strong>{key}</strong>
                        </TableCell>
                        <TableCell>
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
            {check.observed_value !== undefined && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="body2">
                  <strong>Observed Value:</strong> {String(check.observed_value)}
                </Typography>
              </Box>
            )}
            {check.expected_value !== undefined && (
              <Box sx={{ mt: 1 }}>
                <Typography variant="body2">
                  <strong>Expected Value:</strong> {String(check.expected_value)}
                </Typography>
              </Box>
            )}
            {check.severity && (
              <Box sx={{ mt: 1 }}>
                <Chip
                  label={`Severity: ${check.severity}`}
                  size="small"
                  color={check.severity === 'HIGH' || check.severity === 'CRITICAL' ? 'error' : 'warning'}
                />
              </Box>
            )}
          </Box>
        </Collapse>
      )}
    </Paper>
  )
}

