/**
 * Data Quality Dashboard Page
 *
 * Comprehensive data quality dashboard with:
 * - DQ run overview with statistics and metrics
 * - DQ metrics display with visualizations
 * - DQ check results display with filtering
 * - DQ run scheduling
 */

import React, { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Button,
  Paper,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  LinearProgress,
  Card,
  CardContent,
} from '@mui/material'
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  ArrowForward as ArrowForwardIcon,
  Assessment as AssessmentIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material'
import { useDQRuns } from '@/hooks/useDQRuns'
import { useRunDQRun } from '@/hooks/useRunDQRun'
import { useAssets } from '@/hooks/useAssets'
import { useDatasets } from '@/hooks'
import type {
  DQRun,
  DQRunStatus,
  DQOverallStatus,
  DQEngine,
  RunDQRunRequest,
} from '@/lib/api/data-quality'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState, NoResultsEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import { formatDistanceToNow } from 'date-fns'

/**
 * Get DQ status badge variant
 */
function getDQStatusBadgeVariant(
  status?: DQOverallStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    case 'UNKNOWN':
      return 'neutral'
    default:
      return 'neutral'
  }
}

/**
 * Get DQ run status badge variant
 */
function getDQRunStatusBadgeVariant(status: DQRunStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
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
 * Get DQ engine badge color
 */
function getDQEngineColor(engine: DQEngine): 'default' | 'primary' | 'secondary' {
  switch (engine) {
    case 'GREAT_EXPECTATIONS':
      return 'primary'
    case 'SODA':
      return 'secondary'
    default:
      return 'default'
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

/**
 * Data Quality Dashboard Page Component
 */
export const DataQualityDashboardPage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Filter state
  const [statusFilter, setStatusFilter] = useState<DQRunStatus | ''>('')
  const [overallStatusFilter, setOverallStatusFilter] = useState<DQOverallStatus | ''>('')
  const [engineFilter, setEngineFilter] = useState<DQEngine | ''>('')
  const [assetIdFilter, setAssetIdFilter] = useState<string>('')

  // Sorting state
  const [ordering, setOrdering] = useState<string>('-created_at')

  // Modal state
  const [isRunDialogOpen, setIsRunDialogOpen] = useState(false)
  const [isScheduleDialogOpen, setIsScheduleDialogOpen] = useState(false)
  const [selectedAssetId, setSelectedAssetId] = useState<string>('')
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('')
  const [selectedProfileKey, setSelectedProfileKey] = useState<string>('')

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: Record<string, any> = {
      page,
      page_size: pageSize,
      ordering,
    }

    if (statusFilter) {
      params.status = statusFilter
    }
    if (assetIdFilter.trim()) {
      params.asset_id = assetIdFilter.trim()
    }

    return params
  }, [page, pageSize, ordering, statusFilter, assetIdFilter])

  // Fetch DQ runs
  const { data, isLoading, error, refetch, isFetching } = useDQRuns(queryParams)

  // Fetch assets for run creation
  const { data: assetsData } = useAssets({ page_size: 100 })

  // Fetch datasets for run creation
  const { data: datasetsData } = useDatasets({ page_size: 100 })

  // Run DQ run mutation
  const runDQRun = useRunDQRun({
    onSuccess: (run) => {
      setIsRunDialogOpen(false)
      setSelectedAssetId('')
      setSelectedDatasetId('')
      setSelectedProfileKey('')
      // Navigate to run detail page (if exists) or refresh
      refetch()
    },
    onError: (error) => {
      console.error('Failed to run DQ check:', error)
    },
  })

  // Calculate overview statistics
  const overviewStats = useMemo(() => {
    if (!data?.results) {
      return {
        totalRuns: 0,
        passedRuns: 0,
        warningRuns: 0,
        failedRuns: 0,
        runningRuns: 0,
        averageScore: 0,
        totalChecks: 0,
        passedChecks: 0,
        failedChecks: 0,
        warningChecks: 0,
      }
    }

    const runs = data.results
    let totalScore = 0
    let scoredRuns = 0
    let totalChecks = 0
    let passedChecks = 0
    let failedChecks = 0
    let warningChecks = 0

    // Count runs by status
    const passedRuns = runs.filter((r) => r.overall_status === 'PASS').length
    const warningRuns = runs.filter((r) => r.overall_status === 'WARN').length
    const failedRuns = runs.filter((r) => r.overall_status === 'FAIL').length
    const runningRuns = runs.filter((r) => r.status === 'RUNNING' || r.status === 'PENDING').length

    // Calculate average score and check statistics
    runs.forEach((run) => {
      if (run.quality_score !== null && run.quality_score !== undefined) {
        totalScore += run.quality_score
        scoredRuns++
      }

      if (run.checks_json && Array.isArray(run.checks_json)) {
        run.checks_json.forEach((check) => {
          totalChecks++
          const checkStatus = check.status
          if (checkStatus === 'PASS') passedChecks++
          else if (checkStatus === 'FAIL') failedChecks++
          else if (checkStatus === 'WARN') warningChecks++
        })
      }
    })

    return {
      totalRuns: runs.length,
      passedRuns,
      warningRuns,
      failedRuns,
      runningRuns,
      averageScore: scoredRuns > 0 ? totalScore / scoredRuns : 0,
      totalChecks,
      passedChecks,
      failedChecks,
      warningChecks,
    }
  }, [data?.results])

  // Get recent runs with issues
  const recentRunsWithIssues = useMemo(() => {
    if (!data?.results) return []
    return data.results
      .filter((run) => run.overall_status === 'FAIL' || run.overall_status === 'WARN')
      .slice(0, 5)
  }, [data?.results])

  // Handle run DQ check
  const handleRunDQCheck = useCallback(async () => {
    if (!selectedAssetId && !selectedDatasetId) return

    try {
      const request: RunDQRunRequest = {
        asset_id: selectedAssetId || undefined,
        dataset_id: selectedDatasetId || undefined,
        profile_key: selectedProfileKey || undefined,
      }

      await runDQRun.mutateAsync(request)
    } catch (error) {
      console.error('Failed to run DQ check:', error)
    }
  }, [selectedAssetId, selectedDatasetId, selectedProfileKey, runDQRun])

  // Handle schedule DQ run (placeholder - will need backend API)
  const handleScheduleDQRun = useCallback(() => {
    // TODO: Implement scheduling API call
    setIsScheduleDialogOpen(false)
    setSelectedAssetId('')
    setSelectedDatasetId('')
    setSelectedProfileKey('')
  }, [])

  // Filter runs by overall status and engine
  const filteredRuns = useMemo(() => {
    if (!data?.results) return []
    let filtered = data.results

    if (overallStatusFilter) {
      filtered = filtered.filter((run) => run.overall_status === overallStatusFilter)
    }

    if (engineFilter) {
      filtered = filtered.filter((run) => run.engine === engineFilter)
    }

    return filtered
  }, [data?.results, overallStatusFilter, engineFilter])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading data quality dashboard..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (error) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load data quality dashboard"
            message={error.message || 'An error occurred while loading data quality data.'}
            onRetry={() => refetch()}
          />
        </Box>
      </Container>
    )
  }

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Data Quality Dashboard
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Monitor data quality runs, metrics, and check results
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetch()} disabled={isFetching}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Button
              variant="outlined"
              startIcon={<ScheduleIcon />}
              onClick={() => setIsScheduleDialogOpen(true)}
            >
              Schedule Run
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setIsRunDialogOpen(true)}
            >
              Run DQ Check
            </Button>
          </Box>
        </Box>

        {/* DQ Overview */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Total Runs
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 600 }}>
                  {overviewStats.totalRuns}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Average Score
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="h4" sx={{ fontWeight: 600 }}>
                    {Math.round(overviewStats.averageScore)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    / 100
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={overviewStats.averageScore}
                  sx={{ mt: 1 }}
                  color={overviewStats.averageScore >= 80 ? 'success' : overviewStats.averageScore >= 60 ? 'warning' : 'error'}
                />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Passed Runs
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CheckCircleIcon color="success" />
                  <Typography variant="h4" sx={{ fontWeight: 600 }}>
                    {overviewStats.passedRuns}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Failed Runs
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ErrorIcon color="error" />
                  <Typography variant="h4" sx={{ fontWeight: 600 }}>
                    {overviewStats.failedRuns}
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* DQ Metrics */}
        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <AssessmentIcon fontSize="small" />
            DQ Metrics
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Check Statistics
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="body2">Total Checks</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {overviewStats.totalChecks}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CheckCircleIcon color="success" fontSize="small" />
                      <Typography variant="body2">Passed</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                      {overviewStats.passedChecks}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <WarningIcon color="warning" fontSize="small" />
                      <Typography variant="body2">Warnings</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: 'warning.main' }}>
                      {overviewStats.warningChecks}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <ErrorIcon color="error" fontSize="small" />
                      <Typography variant="body2">Failed</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: 'error.main' }}>
                      {overviewStats.failedChecks}
                    </Typography>
                  </Box>
                  {overviewStats.totalChecks > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <LinearProgress
                        variant="determinate"
                        value={(overviewStats.passedChecks / overviewStats.totalChecks) * 100}
                        sx={{ height: 8, borderRadius: 1 }}
                        color="success"
                      />
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                        Pass Rate: {Math.round((overviewStats.passedChecks / overviewStats.totalChecks) * 100)}%
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Run Status Breakdown
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CheckCircleIcon color="success" fontSize="small" />
                      <Typography variant="body2">Passed</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {overviewStats.passedRuns}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <WarningIcon color="warning" fontSize="small" />
                      <Typography variant="body2">Warnings</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {overviewStats.warningRuns}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <ErrorIcon color="error" fontSize="small" />
                      <Typography variant="body2">Failed</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {overviewStats.failedRuns}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <InfoIcon color="info" fontSize="small" />
                      <Typography variant="body2">Running</Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {overviewStats.runningRuns}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </Grid>
          </Grid>
        </Paper>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Run Status</InputLabel>
              <Select
                value={statusFilter}
                label="Run Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value as DQRunStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All Statuses</em>
                </MenuItem>
                <MenuItem value="PENDING">Pending</MenuItem>
                <MenuItem value="RUNNING">Running</MenuItem>
                <MenuItem value="SUCCEEDED">Succeeded</MenuItem>
                <MenuItem value="FAILED">Failed</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Overall Status</InputLabel>
              <Select
                value={overallStatusFilter}
                label="Overall Status"
                onChange={(e) => {
                  setOverallStatusFilter(e.target.value as DQOverallStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All Statuses</em>
                </MenuItem>
                <MenuItem value="PASS">Pass</MenuItem>
                <MenuItem value="WARN">Warning</MenuItem>
                <MenuItem value="FAIL">Fail</MenuItem>
                <MenuItem value="UNKNOWN">Unknown</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Engine</InputLabel>
              <Select
                value={engineFilter}
                label="Engine"
                onChange={(e) => {
                  setEngineFilter(e.target.value as DQEngine | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All Engines</em>
                </MenuItem>
                <MenuItem value="GREAT_EXPECTATIONS">Great Expectations</MenuItem>
                <MenuItem value="SODA">Soda</MenuItem>
              </Select>
            </FormControl>

            <TextField
              size="small"
              label="Asset ID"
              value={assetIdFilter}
              onChange={(e) => {
                setAssetIdFilter(e.target.value)
                setPage(1)
              }}
              placeholder="Filter by asset ID"
              sx={{ minWidth: 200 }}
            />
          </Box>
        </Paper>

        {/* Recent Runs with Issues */}
        {recentRunsWithIssues.length > 0 && (
          <Paper sx={{ p: 3, mb: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              Recent Runs with Issues
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Run ID</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Overall Status</TableCell>
                    <TableCell>Engine</TableCell>
                    <TableCell>Quality Score</TableCell>
                    <TableCell>Profile</TableCell>
                    <TableCell>Completed</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recentRunsWithIssues.map((run) => (
                    <TableRow
                      key={run.id}
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/data-quality/runs/${run.id}`)}
                    >
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                        {run.id.substring(0, 8)}...
                      </TableCell>
                      <TableCell>
                        <Badge variant={getDQRunStatusBadgeVariant(run.status)} size="sm">
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={getDQStatusBadgeVariant(run.overall_status)} size="sm">
                          {run.overall_status || '—'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={run.engine === 'GREAT_EXPECTATIONS' ? 'GX' : 'Soda'}
                          size="small"
                          color={getDQEngineColor(run.engine)}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        {run.quality_score !== null && run.quality_score !== undefined ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {Math.round(run.quality_score)}
                            </Typography>
                            <LinearProgress
                              variant="determinate"
                              value={run.quality_score}
                              sx={{ width: 50, height: 6, borderRadius: 1 }}
                              color={run.quality_score >= 80 ? 'success' : run.quality_score >= 60 ? 'warning' : 'error'}
                            />
                          </Box>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                          {run.profile_key}
                        </Typography>
                      </TableCell>
                      <TableCell>{formatDate(run.completed_at)}</TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/data-quality/runs/${run.id}`)
                          }}
                        >
                          <ArrowForwardIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        )}

        {/* DQ Runs List */}
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            DQ Runs
          </Typography>
          {filteredRuns.length === 0 ? (
            <NoResultsEmptyState
              title="No DQ runs found"
              description="Try adjusting your filters or run a new DQ check."
            />
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Run ID</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Overall Status</TableCell>
                    <TableCell>Engine</TableCell>
                    <TableCell>Quality Score</TableCell>
                    <TableCell>Checks</TableCell>
                    <TableCell>Profile</TableCell>
                    <TableCell>Completed</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredRuns.map((run) => {
                    const checks = run.checks_json || []
                    const passedChecks = checks.filter((c) => c.status === 'PASS').length
                    const failedChecks = checks.filter((c) => c.status === 'FAIL').length
                    const warningChecks = checks.filter((c) => c.status === 'WARN').length

                    return (
                      <TableRow
                        key={run.id}
                        sx={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/data-quality/runs/${run.id}`)}
                      >
                        <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                          {run.id.substring(0, 8)}...
                        </TableCell>
                        <TableCell>
                          <Badge variant={getDQRunStatusBadgeVariant(run.status)} size="sm">
                            {run.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getDQStatusBadgeVariant(run.overall_status)} size="sm">
                            {run.overall_status || '—'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={run.engine === 'GREAT_EXPECTATIONS' ? 'GX' : 'Soda'}
                            size="small"
                            color={getDQEngineColor(run.engine)}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>
                          {run.quality_score !== null && run.quality_score !== undefined ? (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                {Math.round(run.quality_score)}
                              </Typography>
                              <LinearProgress
                                variant="determinate"
                                value={run.quality_score}
                                sx={{ width: 50, height: 6, borderRadius: 1 }}
                                color={run.quality_score >= 80 ? 'success' : run.quality_score >= 60 ? 'warning' : 'error'}
                              />
                            </Box>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell>
                          {checks.length > 0 ? (
                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                              {passedChecks > 0 && (
                                <Chip
                                  label={`${passedChecks} Pass`}
                                  size="small"
                                  color="success"
                                  variant="outlined"
                                />
                              )}
                              {warningChecks > 0 && (
                                <Chip
                                  label={`${warningChecks} Warn`}
                                  size="small"
                                  color="warning"
                                  variant="outlined"
                                />
                              )}
                              {failedChecks > 0 && (
                                <Chip
                                  label={`${failedChecks} Fail`}
                                  size="small"
                                  color="error"
                                  variant="outlined"
                                />
                              )}
                            </Box>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                            {run.profile_key}
                          </Typography>
                        </TableCell>
                        <TableCell>{formatDate(run.completed_at)}</TableCell>
                        <TableCell align="right">
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/data-quality/runs/${run.id}`)
                            }}
                          >
                            <ArrowForwardIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* Pagination */}
          {data && data.count > pageSize && (
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
              <EnhancedPagination
                count={Math.ceil(data.count / pageSize)}
                page={page}
                onChange={(_, newPage) => setPage(newPage)}
                pageSize={pageSize}
                onPageSizeChange={setPageSize}
                showPageSizeSelector
              />
            </Box>
          )}
        </Paper>

        {/* Run DQ Check Dialog */}
        <Dialog open={isRunDialogOpen} onClose={() => setIsRunDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Run Data Quality Check</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
              <FormControl fullWidth>
                <InputLabel>Asset</InputLabel>
                <Select
                  value={selectedAssetId}
                  label="Asset"
                  onChange={(e) => {
                    setSelectedAssetId(e.target.value)
                    setSelectedDatasetId('')
                  }}
                >
                  <MenuItem value="">
                    <em>Select an asset</em>
                  </MenuItem>
                  {assetsData?.results.map((asset) => (
                    <MenuItem key={asset.id} value={asset.id}>
                      {asset.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl fullWidth>
                <InputLabel>Dataset (Optional)</InputLabel>
                <Select
                  value={selectedDatasetId}
                  label="Dataset (Optional)"
                  onChange={(e) => setSelectedDatasetId(e.target.value)}
                  disabled={!selectedAssetId}
                >
                  <MenuItem value="">
                    <em>Select a dataset</em>
                  </MenuItem>
                  {datasetsData?.results
                    .filter((dataset) => !selectedAssetId || dataset.asset_id === selectedAssetId)
                    .map((dataset) => (
                      <MenuItem key={dataset.id} value={dataset.id}>
                        {dataset.name}
                      </MenuItem>
                    ))}
                </Select>
              </FormControl>

              <TextField
                fullWidth
                label="Profile Key (Optional)"
                value={selectedProfileKey}
                onChange={(e) => setSelectedProfileKey(e.target.value)}
                placeholder="e.g., intake_basic_gx"
                helperText="Leave empty to use tenant default or platform default"
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsRunDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleRunDQCheck}
              disabled={runDQRun.isPending || (!selectedAssetId && !selectedDatasetId)}
            >
              {runDQRun.isPending ? 'Running...' : 'Run Check'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Schedule DQ Run Dialog */}
        <Dialog open={isScheduleDialogOpen} onClose={() => setIsScheduleDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Schedule Data Quality Run</DialogTitle>
          <DialogContent>
            <Alert severity="info" sx={{ mb: 2 }}>
              Scheduling functionality will be implemented in a future release.
            </Alert>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
              <FormControl fullWidth>
                <InputLabel>Asset</InputLabel>
                <Select
                  value={selectedAssetId}
                  label="Asset"
                  onChange={(e) => setSelectedAssetId(e.target.value)}
                >
                  <MenuItem value="">
                    <em>Select an asset</em>
                  </MenuItem>
                  {assetsData?.results.map((asset) => (
                    <MenuItem key={asset.id} value={asset.id}>
                      {asset.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsScheduleDialogOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={handleScheduleDQRun} disabled>
              Schedule (Coming Soon)
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

DataQualityDashboardPage.displayName = 'DataQualityDashboardPage'

