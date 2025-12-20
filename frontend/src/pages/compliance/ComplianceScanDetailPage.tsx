/**
 * Compliance Scan Detail Page
 *
 * Comprehensive compliance scan detail page with:
 * - Scan information and metadata
 * - Scan results display (overall status, risk level, compliance score)
 * - Violations with details (severity, type, description)
 * - Remediation suggestions
 * - Scan timeline
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
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Security as SecurityIcon,
  Assessment as AssessmentIcon,
  Timeline as TimelineIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import { useComplianceScan } from '@/hooks/useComplianceScan'
import { useComplianceScanResults } from '@/hooks/useComplianceScanResults'
import { useAsset } from '@/hooks/useAssets'
import { useDataset } from '@/hooks/useDatasets'
import type {
  ComplianceScan,
  OverallComplianceStatus,
  RiskLevel,
  ComplianceRegulation,
} from '@/lib/api/compliance'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import { ViolationsList } from '@/components/compliance/ViolationsList'

/**
 * Get compliance status badge variant
 */
function getComplianceStatusBadgeVariant(
  status?: OverallComplianceStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get risk level badge variant
 */
function getRiskLevelBadgeVariant(riskLevel?: RiskLevel): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!riskLevel) return 'neutral'
  switch (riskLevel) {
    case 'NONE':
    case 'LOW':
      return 'success'
    case 'MEDIUM':
      return 'warning'
    case 'HIGH':
    case 'CRITICAL':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get scan status badge variant
 */
function getScanStatusBadgeVariant(status: ComplianceScan['status']): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (status) {
    case 'SUCCEEDED':
      return 'success'
    case 'RUNNING':
    case 'PENDING':
      return 'info'
    case 'FAILED':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get compliance status icon
 */
function getComplianceStatusIcon(status?: OverallComplianceStatus) {
  switch (status) {
    case 'PASS':
      return <CheckCircleIcon color="success" />
    case 'WARN':
      return <WarningIcon color="warning" />
    case 'FAIL':
      return <ErrorIcon color="error" />
    default:
      return <InfoIcon color="action" />
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return format(new Date(dateString), 'PPpp')
  } catch {
    return dateString
  }
}

/**
 * Format relative date for display
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
 * Compliance Scan Detail Page Component
 */
export const ComplianceScanDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Fetch scan data
  const {
    data: scan,
    isLoading: isLoadingScan,
    error: scanError,
    refetch: refetchScan,
  } = useComplianceScan(id!)

  // Fetch scan results (only if scan succeeded)
  const {
    data: results,
    isLoading: isLoadingResults,
    error: resultsError,
  } = useComplianceScanResults(scan?.id, {
    enabled: scan?.status === 'SUCCEEDED',
  })

  // Fetch associated asset if available
  const {
    data: asset,
    isLoading: isLoadingAsset,
  } = useAsset(scan?.asset || null, {
    enabled: !!scan?.asset,
  })

  // Fetch associated dataset if available
  const {
    data: dataset,
    isLoading: isLoadingDataset,
  } = useDataset(scan?.dataset || null, {
    enabled: !!scan?.dataset,
  })

  // Calculate violation statistics
  const violationStats = useMemo(() => {
    if (!results?.violations) {
      return {
        total: 0,
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
        info: 0,
      }
    }

    return results.violations.reduce(
      (acc, violation) => {
        acc.total++
        const severity = violation.severity?.toUpperCase() || ''
        if (severity.includes('CRITICAL')) acc.critical++
        else if (severity.includes('HIGH')) acc.high++
        else if (severity.includes('MEDIUM')) acc.medium++
        else if (severity.includes('LOW')) acc.low++
        else acc.info++
        return acc
      },
      { total: 0, critical: 0, high: 0, medium: 0, low: 0, info: 0 }
    )
  }, [results?.violations])

  // Loading state
  if (isLoadingScan) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading compliance scan..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (scanError || !scan) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load compliance scan"
            message={scanError?.message || 'Compliance scan not found'}
            onRetry={() => refetchScan()}
          />
        </Box>
      </Container>
    )
  }

  const isScanRunning = scan.status === 'RUNNING' || scan.status === 'PENDING'
  const isScanCompleted = scan.status === 'SUCCEEDED'
  const isScanFailed = scan.status === 'FAILED'

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={() => navigate('/compliance')} size="small">
              <ArrowBackIcon />
            </IconButton>
            <Box>
              <Typography variant="h4" gutterBottom>
                Compliance Scan Details
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                {scan.id}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetchScan()} size="small">
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Scan Status Alert */}
        {isScanRunning && (
          <Alert severity="info" sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <CircularProgress size={20} />
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  Scan is {scan.status.toLowerCase()}
                </Typography>
                <Typography variant="body2">
                  Results will be available once the scan completes.
                </Typography>
              </Box>
            </Box>
          </Alert>
        )}

        {isScanFailed && (
          <Alert severity="error" sx={{ mb: 3 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Scan failed
            </Typography>
            <Typography variant="body2">
              The compliance scan encountered an error and could not complete.
            </Typography>
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* Scan Information */}
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                <InfoIcon fontSize="small" />
                Scan Information
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    Status
                  </Typography>
                  <Badge variant={getScanStatusBadgeVariant(scan.status)} size="sm">
                    {scan.status}
                  </Badge>
                </Box>

                {scan.overall_status && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Overall Status
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                      {getComplianceStatusIcon(scan.overall_status)}
                      <Badge variant={getComplianceStatusBadgeVariant(scan.overall_status)} size="sm">
                        {scan.overall_status}
                      </Badge>
                    </Box>
                  </Box>
                )}

                {scan.risk_level && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Risk Level
                    </Typography>
                    <Badge variant={getRiskLevelBadgeVariant(scan.risk_level)} size="sm">
                      {scan.risk_level}
                    </Badge>
                  </Box>
                )}

                {scan.regulations && scan.regulations.length > 0 && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      Regulations
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {scan.regulations.map((reg, index) => (
                        <Chip key={index} label={reg} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Box>
                )}

                {scan.started_at && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Started
                    </Typography>
                    <Typography variant="body2">{formatRelativeDate(scan.started_at)}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(scan.started_at)}
                    </Typography>
                  </Box>
                )}

                {scan.completed_at && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Completed
                    </Typography>
                    <Typography variant="body2">{formatRelativeDate(scan.completed_at)}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(scan.completed_at)}
                    </Typography>
                  </Box>
                )}

                {scan.created_at && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Created
                    </Typography>
                    <Typography variant="body2">{formatRelativeDate(scan.created_at)}</Typography>
                  </Box>
                )}
              </Box>
            </Paper>

            {/* Associated Resources */}
            {(asset || dataset) && (
              <Paper sx={{ p: 3, mt: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  Associated Resources
                </Typography>
                <Divider sx={{ mb: 2 }} />
                {asset && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                      Asset
                    </Typography>
                    <Button
                      size="small"
                      onClick={() => navigate(`/assets/${asset.id}`)}
                      sx={{ textTransform: 'none' }}
                    >
                      {asset.name}
                    </Button>
                  </Box>
                )}
                {dataset && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">
                      Dataset
                    </Typography>
                    <Button
                      size="small"
                      onClick={() => navigate(`/datasets/${dataset.id}`)}
                      sx={{ textTransform: 'none' }}
                    >
                      {dataset.name}
                    </Button>
                  </Box>
                )}
              </Paper>
            )}
          </Grid>

          {/* Scan Results */}
          <Grid item xs={12} md={8}>
            {isScanCompleted && (
              <>
                {/* Results Summary */}
                {results && (
                  <Paper sx={{ p: 3, mb: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AssessmentIcon fontSize="small" />
                      Scan Results Summary
                    </Typography>
                    <Divider sx={{ mb: 2 }} />

                    <Grid container spacing={3}>
                      {results.compliance_score !== null && results.compliance_score !== undefined && (
                        <Grid item xs={12} sm={6}>
                          <Card variant="outlined">
                            <CardContent>
                              <Typography variant="body2" color="text.secondary" gutterBottom>
                                Compliance Score
                              </Typography>
                              <Typography variant="h4" sx={{ fontWeight: 600 }}>
                                {Math.round(results.compliance_score * 100)}%
                              </Typography>
                              <LinearProgress
                                variant="determinate"
                                value={results.compliance_score * 100}
                                sx={{ mt: 1 }}
                                color={
                                  results.compliance_score >= 0.8
                                    ? 'success'
                                    : results.compliance_score >= 0.6
                                    ? 'warning'
                                    : 'error'
                                }
                              />
                            </CardContent>
                          </Card>
                        </Grid>
                      )}

                      <Grid item xs={12} sm={6}>
                        <Card variant="outlined">
                          <CardContent>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Total Violations
                            </Typography>
                            <Typography variant="h4" sx={{ fontWeight: 600 }}>
                              {violationStats.total}
                            </Typography>
                            {violationStats.total > 0 && (
                              <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                {violationStats.critical > 0 && (
                                  <Chip label={`${violationStats.critical} Critical`} size="small" color="error" />
                                )}
                                {violationStats.high > 0 && (
                                  <Chip label={`${violationStats.high} High`} size="small" color="error" variant="outlined" />
                                )}
                                {violationStats.medium > 0 && (
                                  <Chip label={`${violationStats.medium} Medium`} size="small" color="warning" />
                                )}
                                {violationStats.low > 0 && (
                                  <Chip label={`${violationStats.low} Low`} size="small" color="info" />
                                )}
                              </Box>
                            )}
                          </CardContent>
                        </Card>
                      </Grid>

                      <Grid item xs={12} sm={6}>
                        <Card variant="outlined">
                          <CardContent>
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                              Allowed to Store
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                              {results.allowed_to_store ? (
                                <>
                                  <CheckCircleIcon color="success" />
                                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                    Yes
                                  </Typography>
                                </>
                              ) : (
                                <>
                                  <ErrorIcon color="error" />
                                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                                    No
                                  </Typography>
                                </>
                              )}
                            </Box>
                          </CardContent>
                        </Card>
                      </Grid>
                    </Grid>
                  </Paper>
                )}

                {/* Violations */}
                {isLoadingResults ? (
                  <Paper sx={{ p: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                      <CircularProgress />
                    </Box>
                  </Paper>
                ) : resultsError ? (
                  <Alert severity="warning" sx={{ mb: 3 }}>
                    Could not load scan results: {resultsError.message}
                  </Alert>
                ) : results ? (
                  <Paper sx={{ p: 3, mb: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                      <SecurityIcon fontSize="small" />
                      Violations
                    </Typography>
                    <Divider sx={{ mb: 2 }} />
                    <ViolationsList
                      violations={results.violations}
                      violationDetails={results.violation_details}
                      remediationSuggestions={results.remediation_suggestions}
                    />
                  </Paper>
                ) : null}

                {/* Remediation Suggestions */}
                {results?.remediation_suggestions && results.remediation_suggestions.length > 0 && (
                  <Paper sx={{ p: 3, mb: 3 }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                      Remediation Suggestions
                    </Typography>
                    <Divider sx={{ mb: 2 }} />
                    <Box component="ul" sx={{ pl: 3, m: 0 }}>
                      {results.remediation_suggestions.map((suggestion, index) => (
                        <li key={index} style={{ marginBottom: '0.5rem' }}>
                          <Typography variant="body2">
                            {typeof suggestion === 'string'
                              ? suggestion
                              : suggestion.description || suggestion.title || JSON.stringify(suggestion)}
                          </Typography>
                          {typeof suggestion === 'object' && suggestion.steps && (
                            <Box component="ul" sx={{ pl: 3, mt: 0.5 }}>
                              {Array.isArray(suggestion.steps) &&
                                suggestion.steps.map((step: any, stepIndex: number) => (
                                  <li key={stepIndex}>
                                    <Typography variant="body2" color="text.secondary">
                                      {typeof step === 'string' ? step : step.description || JSON.stringify(step)}
                                    </Typography>
                                  </li>
                                ))}
                            </Box>
                          )}
                        </li>
                      ))}
                    </Box>
                  </Paper>
                )}

                {/* Risk Assessment */}
                {results?.risk_assessment && (
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        Risk Assessment
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.875rem' }}>
                        {JSON.stringify(results.risk_assessment, null, 2)}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Violation Timeline */}
                {results?.violation_timeline && results.violation_timeline.length > 0 && (
                  <Accordion sx={{ mt: 3 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="h6" sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TimelineIcon fontSize="small" />
                        Violation Timeline
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.875rem' }}>
                        {JSON.stringify(results.violation_timeline, null, 2)}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                )}
              </>
            )}

            {!isScanCompleted && !isScanFailed && (
              <Paper sx={{ p: 3 }}>
                <Alert severity="info">
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    Scan in progress
                  </Typography>
                  <Typography variant="body2">
                    Results will be displayed here once the scan completes.
                  </Typography>
                </Alert>
              </Paper>
            )}
          </Grid>
        </Grid>
      </Box>
    </Container>
  )
}

ComplianceScanDetailPage.displayName = 'ComplianceScanDetailPage'

