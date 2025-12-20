/**
 * Compliance Dashboard Page
 *
 * Comprehensive compliance dashboard with:
 * - Compliance overview with statistics and metrics
 * - Compliance scan results display with filtering
 * - Compliance violations display with severity and remediation
 * - Compliance scan scheduling
 */

import React, { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Button,
  Paper,
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
} from '@mui/material'
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  Schedule as ScheduleIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material'
import { useComplianceScans } from '@/hooks/useComplianceScans'
import { useRunComplianceScan } from '@/hooks/useRunComplianceScan'
import { useComplianceScanResults } from '@/hooks/useComplianceScanResults'
import { useAssets } from '@/hooks/useAssets'
import type {
  ComplianceScan,
  ComplianceRunStatus,
  OverallComplianceStatus,
  ComplianceRegulation,
  RiskLevel,
  RunComplianceScanRequest,
} from '@/lib/api/compliance'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import {
  ViolationScanSection,
  ComplianceOverview,
  ComplianceScanList,
} from '@/components/compliance'
import { formatDistanceToNow } from 'date-fns'

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
function getScanStatusBadgeVariant(status: ComplianceRunStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
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
 * Compliance Dashboard Page Component
 */
export const ComplianceDashboardPage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Filter state
  const [statusFilter, setStatusFilter] = useState<ComplianceRunStatus | ''>('')
  const [regulationFilter, setRegulationFilter] = useState<ComplianceRegulation | ''>('')

  // Sorting state
  const [ordering, setOrdering] = useState<string>('-created_at')

  // Modal state
  const [isScanDialogOpen, setIsScanDialogOpen] = useState(false)
  const [isScheduleDialogOpen, setIsScheduleDialogOpen] = useState(false)
  const [selectedAssetId, setSelectedAssetId] = useState<string>('')
  const [selectedRegulations, setSelectedRegulations] = useState<ComplianceRegulation[]>([])

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
    if (regulationFilter) {
      params.regulation = regulationFilter
    }

    return params
  }, [page, pageSize, ordering, statusFilter, regulationFilter])

  // Fetch compliance scans
  const { data, isLoading, error, refetch, isFetching } = useComplianceScans(queryParams)

  // Fetch assets for scan creation
  const { data: assetsData } = useAssets({ page_size: 100 })

  // Run scan mutation
  const runScan = useRunComplianceScan()

  // Calculate overview statistics
  const overviewStats = useMemo(() => {
    if (!data?.results) {
      return {
        totalScans: 0,
        passedScans: 0,
        warningScans: 0,
        failedScans: 0,
        runningScans: 0,
        totalViolations: 0,
        criticalViolations: 0,
        highViolations: 0,
        mediumViolations: 0,
        lowViolations: 0,
      }
    }

    const scans = data.results
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

    // Count violations (we'll need to fetch results for accurate counts, but estimate from risk level)
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
  }, [data?.results])

  // Get recent scans with violations
  const recentScansWithViolations = useMemo(() => {
    if (!data?.results) return []
    return data.results
      .filter((scan) => scan.overall_status === 'FAIL' || scan.overall_status === 'WARN')
      .slice(0, 5)
  }, [data?.results])

  // Handle run scan
  const handleRunScan = useCallback(async () => {
    if (!selectedAssetId) return

    try {
      const request: RunComplianceScanRequest = {
        asset_id: selectedAssetId,
        scan_mode: 'internal',
        applicable_regulations: selectedRegulations.length > 0 ? selectedRegulations : undefined,
      }

      const scan = await runScan.mutateAsync(request)
      setIsScanDialogOpen(false)
      setSelectedAssetId('')
      setSelectedRegulations([])
      // Navigate to scan detail page
      navigate(`/compliance/scans/${scan.id}`)
    } catch (error) {
      console.error('Failed to run scan:', error)
    }
  }, [selectedAssetId, selectedRegulations, runScan, navigate])

  // Handle schedule scan (placeholder - will need backend API)
  const handleScheduleScan = useCallback(() => {
    // TODO: Implement scheduling API call
    setIsScheduleDialogOpen(false)
    setSelectedAssetId('')
    setSelectedRegulations([])
  }, [])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading compliance dashboard..." />
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
            title="Failed to load compliance dashboard"
            message={error.message || 'An error occurred while loading compliance data.'}
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
              Compliance Dashboard
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Monitor compliance scans, violations, and overall compliance status
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
              Schedule Scan
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setIsScanDialogOpen(true)}
            >
              Run Scan
            </Button>
          </Box>
        </Box>

        {/* Compliance Overview */}
        <Box sx={{ mb: 4 }}>
          <ComplianceOverview
            scans={data?.results || []}
            showRunningScans={true}
            showViolationBreakdown={true}
          />
        </Box>

        {/* Recent Violations */}
        {recentScansWithViolations.length > 0 && (
          <Paper sx={{ p: 3, mb: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              Recent Violations
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Scan ID</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Risk Level</TableCell>
                    <TableCell>Regulations</TableCell>
                    <TableCell>Completed</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {recentScansWithViolations.map((scan) => (
                    <TableRow
                      key={scan.id}
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/compliance/scans/${scan.id}`)}
                    >
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                        {scan.id.substring(0, 8)}...
                      </TableCell>
                      <TableCell>
                        <Badge variant={getComplianceStatusBadgeVariant(scan.overall_status)} size="sm">
                          {scan.overall_status || '—'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={getRiskLevelBadgeVariant(scan.risk_level)} size="sm">
                          {scan.risk_level || '—'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {scan.regulations && scan.regulations.length > 0 ? (
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {scan.regulations.slice(0, 2).map((reg, idx) => (
                              <Chip key={idx} label={reg} size="small" />
                            ))}
                            {scan.regulations.length > 2 && (
                              <Chip label={`+${scan.regulations.length - 2}`} size="small" />
                            )}
                          </Box>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>{formatDate(scan.completed_at)}</TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/compliance/scans/${scan.id}`)
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

        {/* Violations Display Section */}
        {recentScansWithViolations.length > 0 && (
          <Paper sx={{ p: 3, mb: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              Violations Details
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {recentScansWithViolations.slice(0, 3).map((scan) => (
                <ViolationScanSection key={scan.id} scan={scan} />
              ))}
            </Box>
          </Paper>
        )}

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value as ComplianceRunStatus | '')
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
              <InputLabel>Regulation</InputLabel>
              <Select
                value={regulationFilter}
                label="Regulation"
                onChange={(e) => {
                  setRegulationFilter(e.target.value as ComplianceRegulation | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All Regulations</em>
                </MenuItem>
                <MenuItem value="GDPR">GDPR</MenuItem>
                <MenuItem value="LGPD">LGPD</MenuItem>
                <MenuItem value="CCPA">CCPA</MenuItem>
                <MenuItem value="HIPAA">HIPAA</MenuItem>
                <MenuItem value="SOX">SOX</MenuItem>
              </Select>
            </FormControl>

            {(statusFilter || regulationFilter) && (
              <Button
                size="small"
                onClick={() => {
                  setStatusFilter('')
                  setRegulationFilter('')
                  setPage(1)
                }}
              >
                Clear Filters
              </Button>
            )}
          </Box>
        </Paper>

        {/* Compliance Scans Table */}
        <ComplianceScanList
          scans={data?.results || []}
          totalCount={data?.count}
          page={page}
          totalPages={data?.total_pages || 1}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={(newSize) => {
            setPageSize(newSize)
            setPage(1)
          }}
          onScanClick={(scan) => navigate(`/compliance/scans/${scan.id}`)}
          emptyMessage="No compliance scans"
          emptyAction={{
            label: 'Run Scan',
            onClick: () => setIsScanDialogOpen(true),
          }}
        />

        {/* Run Scan Dialog */}
        <Dialog open={isScanDialogOpen} onClose={() => setIsScanDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Run Compliance Scan</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              <FormControl fullWidth required>
                <InputLabel>Asset</InputLabel>
                <Select
                  value={selectedAssetId}
                  label="Asset"
                  onChange={(e) => setSelectedAssetId(e.target.value)}
                >
                  {assetsData?.results.map((asset) => (
                    <MenuItem key={asset.id} value={asset.id}>
                      {asset.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl fullWidth>
                <InputLabel>Regulations (Optional)</InputLabel>
                <Select
                  multiple
                  value={selectedRegulations}
                  label="Regulations (Optional)"
                  onChange={(e) => setSelectedRegulations(e.target.value as ComplianceRegulation[])}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {(selected as ComplianceRegulation[]).map((value) => (
                        <Chip key={value} label={value} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  <MenuItem value="GDPR">GDPR</MenuItem>
                  <MenuItem value="LGPD">LGPD</MenuItem>
                  <MenuItem value="CCPA">CCPA</MenuItem>
                  <MenuItem value="HIPAA">HIPAA</MenuItem>
                  <MenuItem value="SOX">SOX</MenuItem>
                </Select>
              </FormControl>

              <Alert severity="info">
                If no regulations are selected, all applicable regulations will be checked based on tenant
                configuration.
              </Alert>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsScanDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleRunScan}
              disabled={!selectedAssetId || runScan.isPending}
            >
              {runScan.isPending ? 'Running...' : 'Run Scan'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Schedule Scan Dialog */}
        <Dialog open={isScheduleDialogOpen} onClose={() => setIsScheduleDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Schedule Compliance Scan</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              <FormControl fullWidth required>
                <InputLabel>Asset</InputLabel>
                <Select
                  value={selectedAssetId}
                  label="Asset"
                  onChange={(e) => setSelectedAssetId(e.target.value)}
                >
                  {assetsData?.results.map((asset) => (
                    <MenuItem key={asset.id} value={asset.id}>
                      {asset.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl fullWidth>
                <InputLabel>Regulations (Optional)</InputLabel>
                <Select
                  multiple
                  value={selectedRegulations}
                  label="Regulations (Optional)"
                  onChange={(e) => setSelectedRegulations(e.target.value as ComplianceRegulation[])}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {(selected as ComplianceRegulation[]).map((value) => (
                        <Chip key={value} label={value} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  <MenuItem value="GDPR">GDPR</MenuItem>
                  <MenuItem value="LGPD">LGPD</MenuItem>
                  <MenuItem value="CCPA">CCPA</MenuItem>
                  <MenuItem value="HIPAA">HIPAA</MenuItem>
                  <MenuItem value="SOX">SOX</MenuItem>
                </Select>
              </FormControl>

              <TextField
                fullWidth
                label="Schedule (Cron Expression)"
                placeholder="0 0 * * * (Daily at midnight)"
                helperText="Enter a cron expression for scheduling (e.g., '0 0 * * *' for daily at midnight)"
              />

              <Alert severity="info">
                Scheduled scans will run automatically at the specified interval. This feature requires backend
                scheduling support.
              </Alert>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsScheduleDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleScheduleScan}
              disabled={!selectedAssetId}
            >
              Schedule Scan
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

ComplianceDashboardPage.displayName = 'ComplianceDashboardPage'

