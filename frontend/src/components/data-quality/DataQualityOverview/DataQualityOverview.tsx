/**
 * DataQualityOverview Component
 *
 * Reusable component for displaying data quality overview statistics and metrics.
 * Shows total runs, passed/warning/failed counts, running runs, and average quality score.
 */

import React, { useMemo } from 'react'
import { Grid, Box, Typography, LinearProgress } from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
} from '@mui/icons-material'
import { Card, CardContent } from '@/components/data-display/Card'
import type { DQRun } from '@/lib/api/data-quality'

export interface DataQualityOverviewStats {
  totalRuns: number
  passedRuns: number
  warningRuns: number
  failedRuns: number
  runningRuns: number
  averageScore: number
}

export interface DataQualityOverviewProps {
  /**
   * DQ runs to calculate statistics from
   */
  runs?: DQRun[]
  /**
   * Pre-calculated statistics (optional, will calculate from runs if not provided)
   */
  stats?: DataQualityOverviewStats
  /**
   * Show running runs card
   * @default true
   */
  showRunningRuns?: boolean
  /**
   * Show average score card
   * @default true
   */
  showAverageScore?: boolean
  /**
   * Custom spacing between cards
   * @default 3
   */
  spacing?: number
}

/**
 * Calculate overview statistics from DQ runs
 */
function calculateStats(runs: DQRun[]): DataQualityOverviewStats {
  if (runs.length === 0) {
    return {
      totalRuns: 0,
      passedRuns: 0,
      warningRuns: 0,
      failedRuns: 0,
      runningRuns: 0,
      averageScore: 0,
    }
  }

  // Count runs by status
  const passedRuns = runs.filter((r) => r.overall_status === 'PASS').length
  const warningRuns = runs.filter((r) => r.overall_status === 'WARN').length
  const failedRuns = runs.filter((r) => r.overall_status === 'FAIL').length
  const runningRuns = runs.filter((r) => r.status === 'RUNNING' || r.status === 'PENDING').length

  // Calculate average quality score
  const scores = runs
    .map((r) => r.quality_score)
    .filter((score): score is number => score !== null && score !== undefined)
  const averageScore = scores.length > 0 ? scores.reduce((sum, score) => sum + score, 0) / scores.length : 0

  return {
    totalRuns: runs.length,
    passedRuns,
    warningRuns,
    failedRuns,
    runningRuns,
    averageScore: Math.round(averageScore * 100) / 100, // Round to 2 decimal places
  }
}

/**
 * Get score color based on value
 */
function getScoreColor(score: number): 'success' | 'warning' | 'error' {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'error'
}

/**
 * DataQualityOverview Component
 *
 * @example
 * ```tsx
 * <DataQualityOverview runs={dqRuns} />
 * ```
 */
export const DataQualityOverview: React.FC<DataQualityOverviewProps> = ({
  runs = [],
  stats,
  showRunningRuns = true,
  showAverageScore = true,
  spacing = 3,
}) => {
  const calculatedStats = useMemo(() => {
    if (stats) {
      return stats
    }
    return calculateStats(runs)
  }, [runs, stats])

  const { totalRuns, passedRuns, warningRuns, failedRuns, runningRuns, averageScore } = calculatedStats

  return (
    <Grid container spacing={spacing}>
      {/* Total Runs */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Total Runs
            </Typography>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {totalRuns}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Passed Runs */}
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
              {passedRuns}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Warning Runs */}
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
              {warningRuns}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Failed Runs */}
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
              {failedRuns}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Running Runs */}
      {showRunningRuns && (
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
                {runningRuns}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Average Score */}
      {showAverageScore && (
        <Grid item xs={12} sm={6} md={showRunningRuns ? 3 : 3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Average Score
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography
                  variant="h4"
                  sx={{
                    fontWeight: 600,
                    color: `${getScoreColor(averageScore)}.main`,
                  }}
                >
                  {averageScore.toFixed(1)}
                </Typography>
                <Box sx={{ flex: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={averageScore}
                    color={getScoreColor(averageScore)}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      )}
    </Grid>
  )
}

