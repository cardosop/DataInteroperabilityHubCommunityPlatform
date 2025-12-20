/**
 * ComplianceOverview Component
 *
 * Reusable component for displaying compliance overview statistics and metrics.
 * Shows total scans, passed/warning/failed counts, running scans, and violation statistics.
 */

import React from 'react'
import { Grid, Box, Typography, Chip } from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material'
import { Card, CardContent } from '@/components/data-display/Card'
import type { ComplianceScan } from '@/lib/api/compliance'

export interface ComplianceOverviewStats {
  totalScans: number
  passedScans: number
  warningScans: number
  failedScans: number
  runningScans: number
  totalViolations: number
  criticalViolations: number
  highViolations: number
  mediumViolations: number
  lowViolations: number
}

export interface ComplianceOverviewProps {
  /**
   * Compliance scans to calculate statistics from
   */
  scans?: ComplianceScan[]
  /**
   * Pre-calculated statistics (optional, will calculate from scans if not provided)
   */
  stats?: ComplianceOverviewStats
  /**
   * Show running scans card
   * @default true
   */
  showRunningScans?: boolean
  /**
   * Show violation breakdown
   * @default true
   */
  showViolationBreakdown?: boolean
  /**
   * Custom spacing between cards
   * @default 3
   */
  spacing?: number
}

/**
 * Calculate overview statistics from compliance scans
 */
function calculateStats(scans: ComplianceScan[]): ComplianceOverviewStats {
  let totalViolations = 0
  let criticalViolations = 0
  let highViolations = 0
  let mediumViolations = 0
  let lowViolations = 0

  // Count scans by status
  const passedScans = scans.filter((s) => s.overall_status === 'PASS').length
  const warningScans = scans.filter((s) => s.overall_status === 'WARN').length
  const failedScans = scans.filter((s) => s.overall_status === 'FAIL').length
  const runningScans = scans.filter((s) => s.status === 'RUNNING' || s.status === 'PENDING').length

  // Count violations (estimate from risk level)
  scans.forEach((scan) => {
    if (scan.risk_level === 'CRITICAL') criticalViolations++
    else if (scan.risk_level === 'HIGH') highViolations++
    else if (scan.risk_level === 'MEDIUM') mediumViolations++
    else if (scan.risk_level === 'LOW') lowViolations++
  })
  totalViolations = criticalViolations + highViolations + mediumViolations + lowViolations

  return {
    totalScans: scans.length,
    passedScans,
    warningScans,
    failedScans,
    runningScans,
    totalViolations,
    criticalViolations,
    highViolations,
    mediumViolations,
    lowViolations,
  }
}

/**
 * ComplianceOverview Component
 *
 * @example
 * ```tsx
 * <ComplianceOverview
 *   scans={complianceScans}
 *   showRunningScans={true}
 *   showViolationBreakdown={true}
 * />
 * ```
 */
export const ComplianceOverview: React.FC<ComplianceOverviewProps> = ({
  scans = [],
  stats,
  showRunningScans = true,
  showViolationBreakdown = true,
  spacing = 3,
}) => {
  // Calculate stats from scans if not provided
  const overviewStats = stats || calculateStats(scans)

  return (
    <Grid container spacing={spacing}>
      {/* Total Scans */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Total Scans
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {overviewStats.totalScans}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Passed Scans */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <CheckCircleIcon color="success" />
              <Typography variant="body2" color="text.secondary">
                Passed
              </Typography>
            </Box>
            <Typography variant="h4" sx={{ fontWeight: 600, color: 'success.main' }}>
              {overviewStats.passedScans}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Warning Scans */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <WarningIcon color="warning" />
              <Typography variant="body2" color="text.secondary">
                Warnings
              </Typography>
            </Box>
            <Typography variant="h4" sx={{ fontWeight: 600, color: 'warning.main' }}>
              {overviewStats.warningScans}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Failed Scans */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <ErrorIcon color="error" />
              <Typography variant="body2" color="text.secondary">
                Failed
              </Typography>
            </Box>
            <Typography variant="h4" sx={{ fontWeight: 600, color: 'error.main' }}>
              {overviewStats.failedScans}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Running Scans */}
      {showRunningScans && overviewStats.runningScans > 0 && (
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <InfoIcon color="info" />
                <Typography variant="body2" color="text.secondary">
                  Running
                </Typography>
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 600, color: 'info.main' }}>
                {overviewStats.runningScans}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Total Violations */}
      {showViolationBreakdown && (
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total Violations
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                {overviewStats.totalViolations}
              </Typography>
              <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {overviewStats.criticalViolations > 0 && (
                  <Chip
                    label={`${overviewStats.criticalViolations} Critical`}
                    size="small"
                    color="error"
                  />
                )}
                {overviewStats.highViolations > 0 && (
                  <Chip
                    label={`${overviewStats.highViolations} High`}
                    size="small"
                    color="error"
                    variant="outlined"
                  />
                )}
                {overviewStats.mediumViolations > 0 && (
                  <Chip
                    label={`${overviewStats.mediumViolations} Medium`}
                    size="small"
                    color="warning"
                    variant="outlined"
                  />
                )}
                {overviewStats.lowViolations > 0 && (
                  <Chip
                    label={`${overviewStats.lowViolations} Low`}
                    size="small"
                    color="info"
                    variant="outlined"
                  />
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      )}
    </Grid>
  )
}

ComplianceOverview.displayName = 'ComplianceOverview'

