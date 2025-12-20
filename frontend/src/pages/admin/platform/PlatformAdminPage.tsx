/**
 * Platform Admin Page
 *
 * Comprehensive platform administration interface with:
 * - Platform overview with statistics and metrics
 * - All tenants display with filtering and management
 * - System metrics display
 * - Tenant management (suspend, activate, view details)
 */

import React, { useState, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Box,
  Typography,
  Button,
  Paper,
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
  Grid,
  Card,
  CardContent,
} from '@mui/material'
import {
  Refresh as RefreshIcon,
  Block as BlockIcon,
  CheckCircle as CheckCircleIcon,
  Visibility as VisibilityIcon,
  Assessment as AssessmentIcon,
  Business as BusinessIcon,
} from '@mui/icons-material'
import { useTenants, useSystemMetrics, useSuspendTenant, useReactivateTenant } from '@/hooks/usePlatformAdmin'
import type { Tenant, TenantStatus, KYCStatus } from '@/lib/api/tenants'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import { formatDistanceToNow } from 'date-fns'

/**
 * Get tenant status badge variant
 */
function getTenantStatusBadgeVariant(status: TenantStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (status) {
    case 'ACTIVE':
      return 'success'
    case 'SUSPENDED':
      return 'warning'
    case 'DELETED':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get KYC status badge variant
 */
function getKYCStatusBadgeVariant(kycStatus: KYCStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (kycStatus) {
    case 'VERIFIED':
      return 'success'
    case 'UNVERIFIED':
      return 'warning'
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
 * Platform Admin Page Component
 */
export const PlatformAdminPage: React.FC = () => {
  const navigate = useNavigate()

  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  // Filter state
  const [statusFilter, setStatusFilter] = useState<TenantStatus | ''>('')
  const [kycFilter, setKycFilter] = useState<KYCStatus | ''>('')
  const [searchQuery, setSearchQuery] = useState('')

  // Modal state
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null)
  const [isSuspendDialogOpen, setIsSuspendDialogOpen] = useState(false)
  const [isReactivateDialogOpen, setIsReactivateDialogOpen] = useState(false)
  const [suspendReason, setSuspendReason] = useState('')
  const [reactivateReason, setReactivateReason] = useState('')

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: Record<string, any> = {
      page,
      page_size: pageSize,
      ordering: '-created_at',
    }

    if (statusFilter) {
      params.status = statusFilter
    }
    if (kycFilter) {
      params.kyc_status = kycFilter
    }
    if (searchQuery) {
      params.search = searchQuery
    }

    return params
  }, [page, pageSize, statusFilter, kycFilter, searchQuery])

  // Fetch tenants
  const { data: tenantsData, isLoading, error, refetch, isFetching } = useTenants(queryParams)

  // Fetch system metrics
  const { data: metricsData, refetch: refetchMetrics } = useSystemMetrics()

  // Mutations
  const suspendTenantMutation = useSuspendTenant({
    onSuccess: () => {
      setIsSuspendDialogOpen(false)
      setSelectedTenant(null)
      setSuspendReason('')
      refetch()
    },
  })

  const reactivateTenantMutation = useReactivateTenant({
    onSuccess: () => {
      setIsReactivateDialogOpen(false)
      setSelectedTenant(null)
      setReactivateReason('')
      refetch()
    },
  })

  // Calculate overview statistics from tenants data
  const overviewStats = useMemo(() => {
    if (!tenantsData?.results) {
      return {
        totalTenants: 0,
        activeTenants: 0,
        suspendedTenants: 0,
        verifiedTenants: 0,
      }
    }

    const tenants = tenantsData.results
    const activeTenants = tenants.filter((t) => t.status === 'ACTIVE').length
    const suspendedTenants = tenants.filter((t) => t.status === 'SUSPENDED').length
    const verifiedTenants = tenants.filter((t) => t.kyc_status === 'VERIFIED').length

    return {
      totalTenants: tenantsData.count || tenants.length,
      activeTenants,
      suspendedTenants,
      verifiedTenants,
    }
  }, [tenantsData])

  // Handle suspend tenant
  const handleSuspendTenant = useCallback(() => {
    if (!selectedTenant) return

    suspendTenantMutation.mutate({
      tenantId: selectedTenant.id,
      data: suspendReason ? { reason: suspendReason } : undefined,
    })
  }, [selectedTenant, suspendReason, suspendTenantMutation])

  // Handle reactivate tenant
  const handleReactivateTenant = useCallback(() => {
    if (!selectedTenant) return

    reactivateTenantMutation.mutate({
      tenantId: selectedTenant.id,
      data: reactivateReason ? { reason: reactivateReason } : undefined,
    })
  }, [selectedTenant, reactivateReason, reactivateTenantMutation])

  // Loading state
  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading platform admin dashboard..." />
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
            title="Failed to load platform admin dashboard"
            message={error.message || 'An error occurred while loading platform data.'}
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
              Platform Administration
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Manage tenants, monitor system metrics, and oversee platform operations
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh Metrics">
              <IconButton onClick={() => refetchMetrics()} disabled={isFetching}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Refresh All">
              <IconButton onClick={() => refetch()} disabled={isFetching}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Platform Overview */}
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <BusinessIcon sx={{ mr: 1, color: 'primary.main' }} />
                  <Typography variant="h6">Total Tenants</Typography>
                </Box>
                <Typography variant="h4">{overviewStats.totalTenants}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <CheckCircleIcon sx={{ mr: 1, color: 'success.main' }} />
                  <Typography variant="h6">Active Tenants</Typography>
                </Box>
                <Typography variant="h4">{overviewStats.activeTenants}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <BlockIcon sx={{ mr: 1, color: 'warning.main' }} />
                  <Typography variant="h6">Suspended</Typography>
                </Box>
                <Typography variant="h4">{overviewStats.suspendedTenants}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <AssessmentIcon sx={{ mr: 1, color: 'info.main' }} />
                  <Typography variant="h6">Verified (KYC)</Typography>
                </Box>
                <Typography variant="h4">{overviewStats.verifiedTenants}</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* System Metrics */}
        {metricsData && (
          <Paper sx={{ p: 3, mb: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              System Metrics
            </Typography>
            <Box
              component="pre"
              sx={{
                p: 2,
                bgcolor: 'grey.100',
                borderRadius: 1,
                overflow: 'auto',
                maxHeight: 400,
                fontSize: '0.75rem',
                fontFamily: 'monospace',
              }}
            >
              {metricsData}
            </Box>
          </Paper>
        )}

        {/* Filters */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              size="small"
              label="Search"
              placeholder="Search tenants..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setPage(1)
              }}
              sx={{ minWidth: 200 }}
            />
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value as TenantStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All Statuses</em>
                </MenuItem>
                <MenuItem value="ACTIVE">Active</MenuItem>
                <MenuItem value="SUSPENDED">Suspended</MenuItem>
                <MenuItem value="DELETED">Deleted</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>KYC Status</InputLabel>
              <Select
                value={kycFilter}
                label="KYC Status"
                onChange={(e) => {
                  setKycFilter(e.target.value as KYCStatus | '')
                  setPage(1)
                }}
              >
                <MenuItem value="">
                  <em>All KYC Statuses</em>
                </MenuItem>
                <MenuItem value="VERIFIED">Verified</MenuItem>
                <MenuItem value="UNVERIFIED">Unverified</MenuItem>
              </Select>
            </FormControl>

            {(statusFilter || kycFilter || searchQuery) && (
              <Button
                size="small"
                onClick={() => {
                  setStatusFilter('')
                  setKycFilter('')
                  setSearchQuery('')
                  setPage(1)
                }}
              >
                Clear Filters
              </Button>
            )}
          </Box>
        </Paper>

        {/* Tenants Table */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            All Tenants
          </Typography>
          {tenantsData?.results && tenantsData.results.length > 0 ? (
            <>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>Slug</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>KYC Status</TableCell>
                      <TableCell>Region</TableCell>
                      <TableCell>Created</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tenantsData.results.map((tenant) => (
                      <TableRow key={tenant.id} hover>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {tenant.name}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                            {tenant.slug}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getTenantStatusBadgeVariant(tenant.status)} size="sm">
                            {tenant.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getKYCStatusBadgeVariant(tenant.kyc_status)} size="sm">
                            {tenant.kyc_status}
                          </Badge>
                        </TableCell>
                        <TableCell>{tenant.region || '—'}</TableCell>
                        <TableCell>{formatDate(tenant.created_at)}</TableCell>
                        <TableCell align="right">
                          <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                            <Tooltip title="View Details">
                              <IconButton
                                size="small"
                                onClick={() => navigate(`/admin/tenants/${tenant.id}`)}
                              >
                                <VisibilityIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            {tenant.status === 'ACTIVE' && (
                              <Tooltip title="Suspend Tenant">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setSelectedTenant(tenant)
                                    setIsSuspendDialogOpen(true)
                                  }}
                                >
                                  <BlockIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            {tenant.status === 'SUSPENDED' && (
                              <Tooltip title="Reactivate Tenant">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setSelectedTenant(tenant)
                                    setIsReactivateDialogOpen(true)
                                  }}
                                >
                                  <CheckCircleIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>

              {/* Pagination */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Showing {tenantsData.results.length} of {tenantsData.count || 0} tenants
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    size="small"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous
                  </Button>
                  <Typography variant="body2" sx={{ alignSelf: 'center', px: 2 }}>
                    Page {page} of {tenantsData.total_pages || 1}
                  </Typography>
                  <Button
                    size="small"
                    disabled={page >= (tenantsData.total_pages || 1)}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </Button>
                </Box>
              </Box>
            </>
          ) : (
            <NoDataEmptyState
              title="No tenants found"
              description="No tenants match the current filters."
              primaryAction={{
                label: 'Clear Filters',
                onClick: () => {
                  setStatusFilter('')
                  setKycFilter('')
                  setSearchQuery('')
                  setPage(1)
                },
              }}
            />
          )}
        </Paper>

        {/* Suspend Tenant Dialog */}
        <Dialog open={isSuspendDialogOpen} onClose={() => setIsSuspendDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Suspend Tenant</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              <Alert severity="warning">
                Suspending a tenant will block write operations for that tenant. Users will still be able to view data
                but cannot make changes.
              </Alert>
              {selectedTenant && (
                <Typography variant="body2">
                  <strong>Tenant:</strong> {selectedTenant.name} ({selectedTenant.slug})
                </Typography>
              )}
              <TextField
                fullWidth
                label="Reason (Optional)"
                placeholder="Enter reason for suspension..."
                value={suspendReason}
                onChange={(e) => setSuspendReason(e.target.value)}
                multiline
                rows={3}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsSuspendDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              color="warning"
              onClick={handleSuspendTenant}
              disabled={suspendTenantMutation.isPending}
            >
              {suspendTenantMutation.isPending ? 'Suspending...' : 'Suspend Tenant'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Reactivate Tenant Dialog */}
        <Dialog open={isReactivateDialogOpen} onClose={() => setIsReactivateDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Reactivate Tenant</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
              <Alert severity="info">
                Reactivating a tenant will restore full access and allow write operations.
              </Alert>
              {selectedTenant && (
                <Typography variant="body2">
                  <strong>Tenant:</strong> {selectedTenant.name} ({selectedTenant.slug})
                </Typography>
              )}
              <TextField
                fullWidth
                label="Reason (Optional)"
                placeholder="Enter reason for reactivation..."
                value={reactivateReason}
                onChange={(e) => setReactivateReason(e.target.value)}
                multiline
                rows={3}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsReactivateDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              color="success"
              onClick={handleReactivateTenant}
              disabled={reactivateTenantMutation.isPending}
            >
              {reactivateTenantMutation.isPending ? 'Reactivating...' : 'Reactivate Tenant'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

PlatformAdminPage.displayName = 'PlatformAdminPage'

