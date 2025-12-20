/**
 * Data Quality Run Detail Page
 *
 * Comprehensive data quality run detail page with:
 * - Run information and metadata
 * - Run results display (overall status, quality score)
 * - Check results with details (status, expectations, observed values)
 * - Data quality metrics (score breakdown, pass rate, trend analysis)
 */

import React, { useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Paper,
  Chip,
  Button,
  IconButton,
  Divider,
  Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  LinearProgress,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Assessment as AssessmentIcon,
  Timeline as TimelineIcon,
  ExpandMore as ExpandMoreIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import { useDQRun } from '@/hooks/useDQRun'
import { useDQRunResults } from '@/hooks/useDQRunResults'
import { useAsset } from '@/hooks/useAssets'
import { useDataset } from '@/hooks/useDatasets'
import type { DQOverallStatus, DQCheckStatus, DQEngine } from '@/lib/api/data-quality'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'

/**
 * Get DQ status badge variant
 */
function getDQStatusBadgeVariant(status?: DQOverallStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    case 'UNKNOWN':
      return 'info'
    default:
      return 'neutral'
  }
}

/**
 * Get check status badge variant
 */
function getCheckStatusBadgeVariant(status?: DQCheckStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    case 'UNKNOWN':
      return 'info'
    default:
      return 'neutral'
  }
}

/**
 * Get quality score color
 */
function getQualityScoreColor(score: number): 'success' | 'warning' | 'error' {
  if (score >= 0.9) return 'success'
  if (score >= 0.7) return 'warning'
  return 'error'
}

/**
 * Format percentage
 */
function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/**
 * Format relative date
 */
function formatRelativeDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

/**
 * Format absolute date
 */
function formatAbsoluteDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return format(new Date(dateString), 'PPpp')
  } catch {
    return dateString
  }
}

/**
 * Data Quality Run Detail Page Component
 */
export const DataQualityRunDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Fetch DQ run data
  const {
    data: run,
    isLoading: isLoadingRun,
    error: runError,
    refetch: refetchRun,
  } = useDQRun(id!)

  // Fetch DQ run results (only if run succeeded)
  const {
    data: results,
    isLoading: isLoadingResults,
    error: resultsError,
  } = useDQRunResults(run?.id, {
    enabled: run?.status === 'SUCCEEDED',
  })

  // Fetch associated asset if available
  const {
    data: asset,
    isLoading: isLoadingAsset,
  } = useAsset(run?.asset || null, {
    enabled: !!run?.asset,
  })

  // Fetch associated dataset if available
  const {
    data: dataset,
    isLoading: isLoadingDataset,
  } = useDataset(run?.dataset || null, {
    enabled: !!run?.dataset,
  })

  // Calculate check statistics
  const checkStats = useMemo(() => {
    if (!results?.checks) {
      return {
        total: 0,
        passed: 0,
        failed: 0,
        warnings: 0,
        unknown: 0,
      }
    }

    return results.checks.reduce(
      (acc, check) => {
        acc.total++
        switch (check.status) {
          case 'PASS':
            acc.passed++
            break
          case 'FAIL':
            acc.failed++
            break
          case 'WARN':
            acc.warnings++
            break
          default:
            acc.unknown++
        }
        return acc
      },
      { total: 0, passed: 0, failed: 0, warnings: 0, unknown: 0 }
    )
  }, [results?.checks])

  // Group checks by status
  const checksByStatus = useMemo(() => {
    if (!results?.checks) return { passed: [], failed: [], warnings: [], unknown: [] }

    return results.checks.reduce(
      (acc, check) => {
        switch (check.status) {
          case 'PASS':
            acc.passed.push(check)
            break
          case 'FAIL':
            acc.failed.push(check)
            break
          case 'WARN':
            acc.warnings.push(check)
            break
          default:
            acc.unknown.push(check)
        }
        return acc
      },
      { passed: [] as typeof results.checks, failed: [] as typeof results.checks, warnings: [] as typeof results.checks, unknown: [] as typeof results.checks }
    )
  }, [results?.checks])

  // Loading state
  if (isLoadingRun) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading data quality run..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (runError || !run) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load data quality run"
            message={runError?.message || 'Data quality run not found.'}
            onRetry={() => refetchRun()}
          />
        </Box>
      </Container>
    )
  }

  const qualityScore = results?.overall_score ?? run.quality_score ?? 0
  const overallStatus = results?.overall_status ?? run.overall_status ?? 'UNKNOWN'

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
          <IconButton onClick={() => navigate('/data-quality')} size="small">
            <ArrowBackIcon />
          </IconButton>
          <Box sx={{ flex: 1 }}>
            <Typography variant="h4" gutterBottom>
              Data Quality Run Details
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Run ID: {run.id.substring(0, 8)}...
            </Typography>
          </Box>
          <Tooltip title="Refresh">
            <IconButton onClick={() => refetchRun()} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>

        {/* Run Information */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <AssessmentIcon />
            <Typography variant="h6">Run Information</Typography>
          </Box>
          <Divider sx={{ my: 2 }} />

          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Status
                </Typography>
                <Badge variant={getDQStatusBadgeVariant(overallStatus)} size="sm">
                  {overallStatus}
                </Badge>
                <Chip
                  label={run.status}
                  size="small"
                  sx={{ ml: 1 }}
                  color={run.status === 'SUCCEEDED' ? 'success' : run.status === 'FAILED' ? 'error' : 'info'}
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Quality Score
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <LinearProgress
                    variant="determinate"
                    value={qualityScore * 100}
                    color={getQualityScoreColor(qualityScore)}
                    sx={{ flex: 1, height: 8, borderRadius: 4 }}
                  />
                  <Typography variant="h6" color={`${getQualityScoreColor(qualityScore)}.main`}>
                    {formatPercentage(qualityScore)}
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Engine
                </Typography>
                <Chip label={run.engine} size="small" />
                {run.profile_key && (
                  <Chip label={`Profile: ${run.profile_key}`} size="small" sx={{ ml: 1 }} variant="outlined" />
                )}
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Started
                </Typography>
                <Typography variant="body1">
                  {formatAbsoluteDate(run.started_at)}
                  {run.started_at && (
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatRelativeDate(run.started_at)})
                    </Typography>
                  )}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Completed
                </Typography>
                <Typography variant="body1">
                  {formatAbsoluteDate(run.completed_at)}
                  {run.completed_at && (
                    <Typography component="span" variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatRelativeDate(run.completed_at)})
                    </Typography>
                  )}
                </Typography>
              </Box>

              {(asset || dataset) && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Resource
                  </Typography>
                  {asset && (
                    <Button
                      size="small"
                      onClick={() => navigate(`/assets/${asset.id}`)}
                      sx={{ textTransform: 'none' }}
                    >
                      Asset: {asset.name}
                    </Button>
                  )}
                  {dataset && (
                    <Button
                      size="small"
                      onClick={() => navigate(`/datasets/${dataset.id}`)}
                      sx={{ textTransform: 'none', ml: asset ? 1 : 0 }}
                    >
                      Dataset: {dataset.name}
                    </Button>
                  )}
                </Box>
              )}
            </Grid>
          </Grid>
        </Paper>

        {/* Data Quality Metrics */}
        {results && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <AssessmentIcon />
              <Typography variant="h6">Data Quality Metrics</Typography>
            </Box>
            <Divider sx={{ my: 2 }} />

            <Grid container spacing={3}>
              {/* Score Breakdown */}
              {results.score_breakdown && (
                <>
                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Total Checks
                        </Typography>
                        <Typography variant="h4" sx={{ fontWeight: 600 }}>
                          {results.score_breakdown.total_checks}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <CheckCircleIcon color="success" />
                          <Typography variant="body2" color="text.secondary">
                            Passed
                          </Typography>
                        </Box>
                        <Typography variant="h4" sx={{ fontWeight: 600, color: 'success.main' }}>
                          {results.score_breakdown.passed_checks}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <ErrorIcon color="error" />
                          <Typography variant="body2" color="text.secondary">
                            Failed
                          </Typography>
                        </Box>
                        <Typography variant="h4" sx={{ fontWeight: 600, color: 'error.main' }}>
                          {results.score_breakdown.failed_checks}
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>

                  {results.score_breakdown.warning_checks > 0 && (
                    <Grid item xs={12} md={4}>
                      <Card>
                        <CardContent>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <WarningIcon color="warning" />
                            <Typography variant="body2" color="text.secondary">
                              Warnings
                            </Typography>
                          </Box>
                          <Typography variant="h4" sx={{ fontWeight: 600, color: 'warning.main' }}>
                            {results.score_breakdown.warning_checks}
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  )}

                  <Grid item xs={12} md={4}>
                    <Card>
                      <CardContent>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Pass Rate
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <LinearProgress
                            variant="determinate"
                            value={results.score_breakdown.pass_rate * 100}
                            color={getQualityScoreColor(results.score_breakdown.pass_rate)}
                            sx={{ flex: 1, height: 8, borderRadius: 4 }}
                          />
                          <Typography variant="h6" color={`${getQualityScoreColor(results.score_breakdown.pass_rate)}.main`}>
                            {formatPercentage(results.score_breakdown.pass_rate)}
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                </>
              )}

              {/* Trend Analysis */}
              {results.trend_analysis && (
                <Grid item xs={12}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <TimelineIcon />
                        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                          Trend Analysis
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                        {results.trend_analysis.direction === 'IMPROVING' && (
                          <Chip
                            icon={<TrendingUpIcon />}
                            label="Improving"
                            color="success"
                            size="small"
                          />
                        )}
                        {results.trend_analysis.direction === 'DEGRADING' && (
                          <Chip
                            icon={<TrendingDownIcon />}
                            label="Degrading"
                            color="error"
                            size="small"
                          />
                        )}
                        {results.trend_analysis.direction === 'STABLE' && (
                          <Chip
                            icon={<TrendingFlatIcon />}
                            label="Stable"
                            color="info"
                            size="small"
                          />
                        )}
                        {results.trend_analysis.change_percentage !== undefined && (
                          <Typography variant="body2" color="text.secondary">
                            Change: {results.trend_analysis.change_percentage > 0 ? '+' : ''}
                            {results.trend_analysis.change_percentage.toFixed(1)}%
                          </Typography>
                        )}
                        {results.trend_analysis.previous_value !== undefined && (
                          <Typography variant="body2" color="text.secondary">
                            Previous: {formatPercentage(results.trend_analysis.previous_value)}
                          </Typography>
                        )}
                        <Typography variant="body2" color="text.secondary">
                          Current: {formatPercentage(results.trend_analysis.current_value)}
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              )}
            </Grid>
          </Paper>
        )}

        {/* Check Results */}
        {isLoadingResults ? (
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          </Paper>
        ) : resultsError ? (
          <Paper sx={{ p: 3 }}>
            <Alert severity="warning">
              Could not load check results: {resultsError.message}
            </Alert>
          </Paper>
        ) : results && results.checks && results.checks.length > 0 ? (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <AssessmentIcon />
              <Typography variant="h6">Check Results</Typography>
              <Chip label={`${checkStats.total} checks`} size="small" />
            </Box>
            <Divider sx={{ my: 2 }} />

            {/* Failed Checks */}
            {checksByStatus.failed.length > 0 && (
              <Accordion defaultExpanded>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                    <ErrorIcon color="error" />
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      Failed Checks ({checksByStatus.failed.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <CheckResultsTable checks={checksByStatus.failed} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Warning Checks */}
            {checksByStatus.warnings.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                    <WarningIcon color="warning" />
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      Warning Checks ({checksByStatus.warnings.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <CheckResultsTable checks={checksByStatus.warnings} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Passed Checks */}
            {checksByStatus.passed.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                    <CheckCircleIcon color="success" />
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      Passed Checks ({checksByStatus.passed.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <CheckResultsTable checks={checksByStatus.passed} />
                </AccordionDetails>
              </Accordion>
            )}

            {/* Unknown Checks */}
            {checksByStatus.unknown.length > 0 && (
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                    <InfoIcon color="info" />
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      Unknown Status ({checksByStatus.unknown.length})
                    </Typography>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <CheckResultsTable checks={checksByStatus.unknown} />
                </AccordionDetails>
              </Accordion>
            )}
          </Paper>
        ) : (
          <Paper sx={{ p: 3 }}>
            <Alert severity="info">No check results available for this run.</Alert>
          </Paper>
        )}

        {/* Recommendations */}
        {results?.recommendations && results.recommendations.length > 0 && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <InfoIcon />
              <Typography variant="h6">Recommendations</Typography>
            </Box>
            <Divider sx={{ my: 2 }} />
            <Box component="ul" sx={{ pl: 3, m: 0 }}>
              {results.recommendations.map((rec, index) => (
                <li key={index}>
                  <Typography variant="body2" sx={{ mb: 1 }}>
                    <strong>{rec.check_name}</strong> ({rec.check_type}): {rec.message}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Action: {rec.action} (Priority: {rec.priority})
                  </Typography>
                </li>
              ))}
            </Box>
          </Paper>
        )}

        {/* Anomalies */}
        {results?.anomalies && results.anomalies.length > 0 && (
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <WarningIcon />
              <Typography variant="h6">Anomalies Detected</Typography>
            </Box>
            <Divider sx={{ my: 2 }} />
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Metric Type</TableCell>
                    <TableCell>Expected</TableCell>
                    <TableCell>Actual</TableCell>
                    <TableCell>Deviation</TableCell>
                    <TableCell>Severity</TableCell>
                    <TableCell>Detected At</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results.anomalies.map((anomaly, index) => (
                    <TableRow key={index}>
                      <TableCell>{anomaly.metric_type}</TableCell>
                      <TableCell>{anomaly.expected_value}</TableCell>
                      <TableCell>{anomaly.actual_value}</TableCell>
                      <TableCell>{anomaly.deviation.toFixed(2)}</TableCell>
                      <TableCell>
                        <Chip
                          label={anomaly.severity}
                          size="small"
                          color={anomaly.severity === 'HIGH' ? 'error' : anomaly.severity === 'MEDIUM' ? 'warning' : 'info'}
                        />
                      </TableCell>
                      <TableCell>{formatAbsoluteDate(anomaly.detected_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        )}
      </Box>
    </Container>
  )
}

/**
 * Check Results Table Component
 */
interface CheckResultsTableProps {
  checks: Array<{
    name: string
    type: string
    status: DQCheckStatus
    result: Record<string, any>
    expectation?: string
    observed_value?: any
    expected_value?: any
    message?: string
    severity?: string
    [key: string]: any
  }>
}

const CheckResultsTable: React.FC<CheckResultsTableProps> = ({ checks }) => {
  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Check Name</TableCell>
            <TableCell>Type</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Expectation</TableCell>
            <TableCell>Observed</TableCell>
            <TableCell>Expected</TableCell>
            <TableCell>Message</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {checks.map((check, index) => (
            <TableRow key={index}>
              <TableCell sx={{ fontWeight: 500 }}>{check.name}</TableCell>
              <TableCell>
                <Chip label={check.type} size="small" variant="outlined" />
              </TableCell>
              <TableCell>
                <Badge variant={getCheckStatusBadgeVariant(check.status)} size="sm">
                  {check.status}
                </Badge>
              </TableCell>
              <TableCell>{check.expectation || '—'}</TableCell>
              <TableCell>
                {check.observed_value !== undefined ? String(check.observed_value) : '—'}
              </TableCell>
              <TableCell>
                {check.expected_value !== undefined ? String(check.expected_value) : '—'}
              </TableCell>
              <TableCell>
                <Typography variant="body2" color="text.secondary">
                  {check.message || '—'}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}

DataQualityRunDetailPage.displayName = 'DataQualityRunDetailPage'

