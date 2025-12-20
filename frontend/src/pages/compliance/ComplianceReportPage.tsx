/**
 * Compliance Report Page
 *
 * Comprehensive compliance report screen with:
 * - Compliance report overview
 * - Compliance metrics (pass rate, violation count, risk score)
 * - Violation breakdown by category
 * - Violation breakdown by jurisdiction
 * - Violation timeline
 * - Asset compliance status
 * - Report export (PDF, CSV)
 * - Report filtering (date range, asset, jurisdiction)
 * - Report scheduling
 */

import React, { useState, useMemo, useCallback } from 'react'
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
  Menu,
  ListItemIcon,
  ListItemText,
  Divider,
  Card,
  CardContent,
} from '@mui/material'
import {
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  Schedule as ScheduleIcon,
  GetApp as GetAppIcon,
  PictureAsPdf as PdfIcon,
  TableChart as CsvIcon,
  FilterList as FilterListIcon,
  CalendarToday as CalendarIcon,
} from '@mui/icons-material'
import { useComplianceReport } from '@/hooks/useComplianceReport'
import { useAssets } from '@/hooks/useAssets'
import type { ComplianceRegulation } from '@/lib/api/compliance'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { exportToCSV } from '@/lib/utils/dataExport'
import { format, parseISO } from 'date-fns'

/**
 * Get risk score color
 */
function getRiskScoreColor(score: number): 'success' | 'warning' | 'error' {
  if (score < 0.3) return 'success'
  if (score < 0.7) return 'warning'
  return 'error'
}

/**
 * Get pass rate color
 */
function getPassRateColor(passRate: number): 'success' | 'warning' | 'error' {
  if (passRate >= 0.9) return 'success'
  if (passRate >= 0.7) return 'warning'
  return 'error'
}

/**
 * Compliance Report Page Component
 */
export const ComplianceReportPage: React.FC = () => {
  // Filter state
  const [startDate, setStartDate] = useState<string>(
    format(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd')
  )
  const [endDate, setEndDate] = useState<string>(format(new Date(), 'yyyy-MM-dd'))
  const [selectedAssetId, setSelectedAssetId] = useState<string>('')
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<ComplianceRegulation | ''>('')

  // UI state
  const [exportMenuAnchor, setExportMenuAnchor] = useState<null | HTMLElement>(null)
  const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false)
  const [scheduleFrequency, setScheduleFrequency] = useState<string>('WEEKLY')
  const [scheduleEmailRecipients, setScheduleEmailRecipients] = useState<string>('')

  // Build report parameters
  const reportParams = useMemo(() => {
    const params: {
      start_date?: string
      end_date?: string
      asset_id?: string
      jurisdiction?: ComplianceRegulation
    } = {}

    if (startDate) {
      params.start_date = `${startDate}T00:00:00Z`
    }
    if (endDate) {
      params.end_date = `${endDate}T23:59:59Z`
    }
    if (selectedAssetId) {
      params.asset_id = selectedAssetId
    }
    if (selectedJurisdiction) {
      params.jurisdiction = selectedJurisdiction
    }

    return params
  }, [startDate, endDate, selectedAssetId, selectedJurisdiction])

  // Fetch compliance report
  const {
    data: reportData,
    isLoading,
    error,
    refetch,
  } = useComplianceReport(reportParams)

  // Fetch assets for filter
  const { data: assetsData } = useAssets({ page_size: 1000 })

  // Handle export menu
  const handleExportMenuOpen = useCallback((event: React.MouseEvent<HTMLElement>) => {
    setExportMenuAnchor(event.currentTarget)
  }, [])

  const handleExportMenuClose = useCallback(() => {
    setExportMenuAnchor(null)
  }, [])

  // Handle CSV export
  const handleExportCSV = useCallback(() => {
    if (!reportData) return

    const exportData = [
      {
        'Report Period Start': reportData.overview.period.start_date,
        'Report Period End': reportData.overview.period.end_date,
        'Total Scans': reportData.overview.total_scans,
        'Pass Rate': `${(reportData.overview.pass_rate * 100).toFixed(2)}%`,
        'Violation Count': reportData.overview.violation_count,
        'Risk Score': reportData.overview.risk_score.toFixed(3),
      },
      ...reportData.violation_breakdown_by_category.map((item) => ({
        Category: item.category,
        'Total Violations': item.count,
        'Critical': item.severity_breakdown.CRITICAL,
        'High': item.severity_breakdown.HIGH,
        'Medium': item.severity_breakdown.MEDIUM,
        'Low': item.severity_breakdown.LOW,
      })),
      ...reportData.violation_breakdown_by_jurisdiction.map((item) => ({
        Jurisdiction: item.jurisdiction,
        'Total Violations': item.total_violations,
        'Pass Rate': `${(item.pass_rate * 100).toFixed(2)}%`,
        'Risk Score': item.risk_score.toFixed(3),
      })),
      ...reportData.asset_compliance_status.map((item) => ({
        'Asset ID': item.asset_id,
        'Asset Name': item.asset_name || 'N/A',
        'Last Scan Date': item.last_scan_date || 'N/A',
        'Overall Status': item.overall_status || 'N/A',
        'Risk Level': item.risk_level || 'N/A',
        'Violation Count': item.violation_count,
        'Compliance Score': item.compliance_score?.toFixed(3) || 'N/A',
      })),
    ]

    exportToCSV(exportData, {
      filename: `compliance-report-${format(new Date(), 'yyyy-MM-dd')}`,
    })

    handleExportMenuClose()
  }, [reportData, handleExportMenuClose])

  // Handle PDF export (placeholder - would use jsPDF or similar in production)
  const handleExportPDF = useCallback(() => {
    if (!reportData) return

    // For now, use browser print functionality
    // In production, this would use jsPDF or a backend service
    const printWindow = window.open('', '_blank')
    if (printWindow) {
      printWindow.document.write(`
        <html>
          <head>
            <title>Compliance Report</title>
            <style>
              body { font-family: Arial, sans-serif; padding: 20px; }
              h1 { color: #333; }
              table { border-collapse: collapse; width: 100%; margin: 20px 0; }
              th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
              th { background-color: #f2f2f2; }
            </style>
          </head>
          <body>
            <h1>Compliance Report</h1>
            <p><strong>Period:</strong> ${format(parseISO(reportData.overview.period.start_date), 'PP')} - ${format(parseISO(reportData.overview.period.end_date), 'PP')}</p>
            <h2>Overview</h2>
            <p>Total Scans: ${reportData.overview.total_scans}</p>
            <p>Pass Rate: ${(reportData.overview.pass_rate * 100).toFixed(2)}%</p>
            <p>Violation Count: ${reportData.overview.violation_count}</p>
            <p>Risk Score: ${reportData.overview.risk_score.toFixed(3)}</p>
            <h2>Violation Breakdown by Category</h2>
            <table>
              <tr><th>Category</th><th>Count</th><th>Critical</th><th>High</th><th>Medium</th><th>Low</th></tr>
              ${reportData.violation_breakdown_by_category.map((item) => `
                <tr>
                  <td>${item.category}</td>
                  <td>${item.count}</td>
                  <td>${item.severity_breakdown.CRITICAL}</td>
                  <td>${item.severity_breakdown.HIGH}</td>
                  <td>${item.severity_breakdown.MEDIUM}</td>
                  <td>${item.severity_breakdown.LOW}</td>
                </tr>
              `).join('')}
            </table>
            <h2>Violation Breakdown by Jurisdiction</h2>
            <table>
              <tr><th>Jurisdiction</th><th>Total Violations</th><th>Pass Rate</th><th>Risk Score</th></tr>
              ${reportData.violation_breakdown_by_jurisdiction.map((item) => `
                <tr>
                  <td>${item.jurisdiction}</td>
                  <td>${item.total_violations}</td>
                  <td>${(item.pass_rate * 100).toFixed(2)}%</td>
                  <td>${item.risk_score.toFixed(3)}</td>
                </tr>
              `).join('')}
            </table>
            <h2>Asset Compliance Status</h2>
            <table>
              <tr><th>Asset ID</th><th>Last Scan Date</th><th>Status</th><th>Risk Level</th><th>Violations</th><th>Compliance Score</th></tr>
              ${reportData.asset_compliance_status.map((item) => `
                <tr>
                  <td>${item.asset_id}</td>
                  <td>${item.last_scan_date ? format(parseISO(item.last_scan_date), 'PP') : 'N/A'}</td>
                  <td>${item.overall_status || 'N/A'}</td>
                  <td>${item.risk_level || 'N/A'}</td>
                  <td>${item.violation_count}</td>
                  <td>${item.compliance_score?.toFixed(3) || 'N/A'}</td>
                </tr>
              `).join('')}
            </table>
          </body>
        </html>
      `)
      printWindow.document.close()
      printWindow.print()
    }

    handleExportMenuClose()
  }, [reportData, handleExportMenuClose])

  // Handle schedule report
  const handleScheduleReport = useCallback(() => {
    // TODO: Implement scheduling API call when backend is available
    setScheduleDialogOpen(false)
    setScheduleFrequency('WEEKLY')
    setScheduleEmailRecipients('')
  }, [])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Generating compliance report..." />
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
            title="Failed to generate compliance report"
            message={error.message || 'An error occurred while generating the compliance report.'}
            onRetry={() => refetch()}
          />
        </Box>
      </Container>
    )
  }

  if (!reportData) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <Alert severity="info">No compliance data available for the selected period.</Alert>
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
              Compliance Report
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Comprehensive compliance analysis and reporting
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => refetch()}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Button
              variant="outlined"
              startIcon={<ScheduleIcon />}
              onClick={() => setScheduleDialogOpen(true)}
            >
              Schedule Report
            </Button>
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              onClick={handleExportMenuOpen}
            >
              Export
            </Button>
            <Menu
              anchorEl={exportMenuAnchor}
              open={Boolean(exportMenuAnchor)}
              onClose={handleExportMenuClose}
            >
              <MenuItem onClick={handleExportCSV}>
                <ListItemIcon>
                  <CsvIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Export as CSV</ListItemText>
              </MenuItem>
              <MenuItem onClick={handleExportPDF}>
                <ListItemIcon>
                  <PdfIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Export as PDF</ListItemText>
              </MenuItem>
            </Menu>
          </Box>
        </Box>

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 4 }}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            <TextField
              label="Start Date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
            <TextField
              label="End Date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
              size="small"
            />
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Asset</InputLabel>
              <Select
                value={selectedAssetId}
                label="Asset"
                onChange={(e) => setSelectedAssetId(e.target.value)}
              >
                <MenuItem value="">All Assets</MenuItem>
                {assetsData?.results.map((asset) => (
                  <MenuItem key={asset.id} value={asset.id}>
                    {asset.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel>Jurisdiction</InputLabel>
              <Select
                value={selectedJurisdiction}
                label="Jurisdiction"
                onChange={(e) => setSelectedJurisdiction(e.target.value as ComplianceRegulation | '')}
              >
                <MenuItem value="">All Jurisdictions</MenuItem>
                <MenuItem value="GDPR">GDPR</MenuItem>
                <MenuItem value="LGPD">LGPD</MenuItem>
                <MenuItem value="CCPA">CCPA</MenuItem>
                <MenuItem value="HIPAA">HIPAA</MenuItem>
                <MenuItem value="SOX">SOX</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Paper>

        {/* Report Overview */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Report Overview
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Period: {format(parseISO(reportData.overview.period.start_date), 'PP')} - {format(parseISO(reportData.overview.period.end_date), 'PP')}
              </Typography>
              <Grid container spacing={3} sx={{ mt: 2 }}>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Total Scans
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 600 }}>
                        {reportData.overview.total_scans}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Pass Rate
                      </Typography>
                      <Typography
                        variant="h4"
                        sx={{
                          fontWeight: 600,
                          color: `${getPassRateColor(reportData.overview.pass_rate)}.main`,
                        }}
                      >
                        {(reportData.overview.pass_rate * 100).toFixed(1)}%
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Violation Count
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 600, color: 'error.main' }}>
                        {reportData.overview.violation_count}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Risk Score
                      </Typography>
                      <Typography
                        variant="h4"
                        sx={{
                          fontWeight: 600,
                          color: `${getRiskScoreColor(reportData.overview.risk_score)}.main`,
                        }}
                      >
                        {reportData.overview.risk_score.toFixed(3)}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Paper>
          </Grid>
        </Grid>

        {/* Violation Breakdown by Category */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Violation Breakdown by Category
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Category</TableCell>
                      <TableCell align="right">Total</TableCell>
                      <TableCell align="right">Critical</TableCell>
                      <TableCell align="right">High</TableCell>
                      <TableCell align="right">Medium</TableCell>
                      <TableCell align="right">Low</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {reportData.violation_breakdown_by_category.map((item) => (
                      <TableRow key={item.category}>
                        <TableCell>{item.category}</TableCell>
                        <TableCell align="right">{item.count}</TableCell>
                        <TableCell align="right">
                          <Chip
                            label={item.severity_breakdown.CRITICAL}
                            size="small"
                            color="error"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={item.severity_breakdown.HIGH}
                            size="small"
                            color="warning"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={item.severity_breakdown.MEDIUM}
                            size="small"
                            color="info"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={item.severity_breakdown.LOW}
                            size="small"
                            color="default"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>

          {/* Violation Breakdown by Jurisdiction */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Violation Breakdown by Jurisdiction
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Jurisdiction</TableCell>
                      <TableCell align="right">Violations</TableCell>
                      <TableCell align="right">Pass Rate</TableCell>
                      <TableCell align="right">Risk Score</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {reportData.violation_breakdown_by_jurisdiction.map((item) => (
                      <TableRow key={item.jurisdiction}>
                        <TableCell>
                          <Chip label={item.jurisdiction} size="small" />
                        </TableCell>
                        <TableCell align="right">{item.total_violations}</TableCell>
                        <TableCell align="right">
                          <Chip
                            label={`${(item.pass_rate * 100).toFixed(1)}%`}
                            size="small"
                            color={getPassRateColor(item.pass_rate)}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={item.risk_score.toFixed(3)}
                            size="small"
                            color={getRiskScoreColor(item.risk_score)}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>

        {/* Violation Timeline */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Violation Timeline
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell align="right">Scans</TableCell>
                      <TableCell align="right">Violations</TableCell>
                      <TableCell align="right">Pass Rate</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {reportData.violation_timeline.map((item) => (
                      <TableRow key={item.date}>
                        <TableCell>{format(parseISO(item.date), 'PP')}</TableCell>
                        <TableCell align="right">{item.scans}</TableCell>
                        <TableCell align="right">{item.violations}</TableCell>
                        <TableCell align="right">
                          <Chip
                            label={`${(item.pass_rate * 100).toFixed(1)}%`}
                            size="small"
                            color={getPassRateColor(item.pass_rate)}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>

        {/* Asset Compliance Status */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Asset Compliance Status
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Asset ID</TableCell>
                      <TableCell>Last Scan Date</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Risk Level</TableCell>
                      <TableCell align="right">Violations</TableCell>
                      <TableCell align="right">Compliance Score</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {reportData.asset_compliance_status.map((item) => (
                      <TableRow key={item.asset_id}>
                        <TableCell>{item.asset_id}</TableCell>
                        <TableCell>
                          {item.last_scan_date
                            ? format(parseISO(item.last_scan_date), 'PP')
                            : 'N/A'}
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={item.overall_status || 'N/A'}
                            size="small"
                            color={
                              item.overall_status === 'PASS'
                                ? 'success'
                                : item.overall_status === 'WARN'
                                  ? 'warning'
                                  : 'error'
                            }
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={item.risk_level || 'N/A'}
                            size="small"
                            color={
                              item.risk_level === 'LOW' || item.risk_level === 'NONE'
                                ? 'success'
                                : item.risk_level === 'MEDIUM'
                                  ? 'warning'
                                  : 'error'
                            }
                          />
                        </TableCell>
                        <TableCell align="right">{item.violation_count}</TableCell>
                        <TableCell align="right">
                          {item.compliance_score !== undefined
                            ? item.compliance_score.toFixed(3)
                            : 'N/A'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        </Grid>

        {/* Schedule Report Dialog */}
        <Dialog open={scheduleDialogOpen} onClose={() => setScheduleDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Schedule Compliance Report</DialogTitle>
          <DialogContent>
            <Box sx={{ pt: 2 }}>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Frequency</InputLabel>
                <Select
                  value={scheduleFrequency}
                  label="Frequency"
                  onChange={(e) => setScheduleFrequency(e.target.value)}
                >
                  <MenuItem value="DAILY">Daily</MenuItem>
                  <MenuItem value="WEEKLY">Weekly</MenuItem>
                  <MenuItem value="MONTHLY">Monthly</MenuItem>
                  <MenuItem value="QUARTERLY">Quarterly</MenuItem>
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label="Email Recipients (comma-separated)"
                value={scheduleEmailRecipients}
                onChange={(e) => setScheduleEmailRecipients(e.target.value)}
                placeholder="user1@example.com, user2@example.com"
                helperText="Enter email addresses separated by commas"
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setScheduleDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleScheduleReport} variant="contained">
              Schedule
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

