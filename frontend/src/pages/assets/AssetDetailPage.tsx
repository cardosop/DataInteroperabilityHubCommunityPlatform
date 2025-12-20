/**
 * Asset Detail Page
 *
 * Comprehensive asset detail page with:
 * - Asset information display
 * - Associated contract display
 * - Associated dataset display
 * - Asset history/audit log
 * - Edit/delete actions
 */

import React, { useState, useCallback } from 'react'
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
  CardHeader,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Stack,
} from '@mui/material'
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  Description as DescriptionIcon,
  Storage as StorageIcon,
  History as HistoryIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import { useAsset, useUpdateAsset, useDeleteAsset } from '@/hooks/useAssets'
import { useRealtimeAssets } from '@/hooks/useRealtimeAssets'
import { useQuery } from '@tanstack/react-query'
import { getContract } from '@/lib/api/contracts'
import { getDataset } from '@/lib/api/datasets'
import { listAuditEvents } from '@/lib/api/audit'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'

/**
 * Asset Detail Page Component
 */
export const AssetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast } = useToastManager()

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  // Fetch asset data
  const {
    data: asset,
    isLoading: isLoadingAsset,
    error: assetError,
    refetch: refetchAsset,
  } = useAsset(id)

  // Subscribe to real-time updates for this specific asset
  useRealtimeAssets({
    assetId: id || undefined,
    showNotifications: true,
    enabled: !!id,
  })

  // Fetch contract if asset has contract_id
  const {
    data: contract,
    isLoading: isLoadingContract,
    error: contractError,
  } = useQuery({
    queryKey: ['contract', asset?.contract_id],
    queryFn: () => getContract(asset!.contract_id!),
    enabled: !!asset?.contract_id,
  })

  // Fetch dataset if asset has dataset_id
  const {
    data: dataset,
    isLoading: isLoadingDataset,
    error: datasetError,
  } = useQuery({
    queryKey: ['dataset', asset?.dataset_id],
    queryFn: () => getDataset(asset!.dataset_id!),
    enabled: !!asset?.dataset_id,
  })

  // Fetch audit events for this asset
  const {
    data: auditEvents,
    isLoading: isLoadingAudit,
    error: auditError,
  } = useQuery({
    queryKey: ['audit-events', 'asset', id],
    queryFn: () =>
      listAuditEvents({
        resource_type: 'ASSET',
        resource_id: id!,
        page_size: 50,
        ordering: '-created_at',
      }),
    enabled: !!id,
  })

  // Delete mutation
  const deleteAssetMutation = useDeleteAsset({
    onSuccess: () => {
      showToast({
        message: 'Asset deleted successfully',
        severity: 'success',
      })
      navigate('/assets')
    },
    onError: (error) => {
      showToast({
        message: error.message || 'Failed to delete asset',
        severity: 'error',
      })
      setIsDeleting(false)
      setDeleteDialogOpen(false)
    },
  })

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!asset || !id) return

    setIsDeleting(true)
    try {
      await deleteAssetMutation.mutateAsync(id)
    } catch (error) {
      // Error handled in onError callback
    }
  }, [asset, id, deleteAssetMutation])

  // Handle edit navigation
  const handleEdit = useCallback(() => {
    if (!id) return
    navigate(`/assets/${id}/edit`)
  }, [id, navigate])

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'success'
      case 'PUBLIC':
        return 'info'
      case 'DRAFT':
        return 'default'
      case 'RETIRED':
        return 'warning'
      default:
        return 'default'
    }
  }

  // Get DQ status color
  const getDQStatusColor = (status: string) => {
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

  // Get compliance status color
  const getComplianceStatusColor = (status: string) => {
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

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'PASS':
        return <CheckCircleIcon fontSize="small" />
      case 'WARN':
        return <WarningIcon fontSize="small" />
      case 'FAIL':
        return <ErrorIcon fontSize="small" />
      default:
        return <HelpIcon fontSize="small" />
    }
  }

  // Loading state
  if (isLoadingAsset) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading asset..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (assetError || !asset) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load asset"
            message={assetError?.message || 'Asset not found'}
            onRetry={() => refetchAsset()}
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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={() => navigate('/assets')} aria-label="Back to assets">
              <ArrowBackIcon />
            </IconButton>
            <Box>
              <Typography variant="h4" gutterBottom>
                {asset.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {asset.key}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <IconButton onClick={() => refetchAsset()} aria-label="Refresh">
              <RefreshIcon />
            </IconButton>
            <Button
              variant="outlined"
              startIcon={<EditIcon />}
              onClick={handleEdit}
            >
              Edit
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => setDeleteDialogOpen(true)}
            >
              Delete
            </Button>
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* Asset Information */}
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Asset Information
              </Typography>
              <Divider sx={{ my: 2 }} />

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Name
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {asset.name}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Key
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {asset.key}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Status
                  </Typography>
                  <Chip
                    label={asset.status}
                    color={getStatusColor(asset.status) as any}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Visibility
                  </Typography>
                  <Chip
                    label={asset.visibility}
                    color={asset.visibility === 'PUBLIC' ? 'primary' : 'default'}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                {asset.domain && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">
                      Domain
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {asset.domain}
                    </Typography>
                  </Grid>
                )}
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Version
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {asset.version}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Data Quality Status
                  </Typography>
                  <Chip
                    icon={getStatusIcon(asset.dq_status)}
                    label={asset.dq_status}
                    color={getDQStatusColor(asset.dq_status) as any}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Compliance Status
                  </Typography>
                  <Chip
                    icon={getStatusIcon(asset.compliance_status)}
                    label={asset.compliance_status}
                    color={getComplianceStatusColor(asset.compliance_status) as any}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                {asset.description && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary">
                      Description
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {asset.description}
                    </Typography>
                  </Grid>
                )}
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Created
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {format(new Date(asset.created_at), 'PPpp')}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatDistanceToNow(new Date(asset.created_at), { addSuffix: true })})
                    </Typography>
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Last Updated
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {format(new Date(asset.updated_at), 'PPpp')}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatDistanceToNow(new Date(asset.updated_at), { addSuffix: true })})
                    </Typography>
                  </Typography>
                </Grid>
              </Grid>
            </Paper>

            {/* Associated Contract */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <DescriptionIcon />
                <Typography variant="h6">Associated Contract</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {isLoadingContract ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : contractError ? (
                <Alert severity="error">
                  Failed to load contract: {contractError instanceof Error ? contractError.message : 'Unknown error'}
                </Alert>
              ) : contract ? (
                <Box>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="text.secondary">
                        Contract Name
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{ mb: 2, cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                        onClick={() => navigate(`/contracts/${contract.id}`)}
                      >
                        {contract.hub_contract_json?.info?.name || contract.id}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="text.secondary">
                        Status
                      </Typography>
                      <Chip
                        label={contract.status}
                        color={contract.status === 'ACTIVE' ? 'success' : 'default'}
                        size="small"
                        sx={{ mb: 2 }}
                      />
                    </Grid>
                    {contract.normalization_status && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="body2" color="text.secondary">
                          Normalization Status
                        </Typography>
                        <Chip
                          label={contract.normalization_status}
                          size="small"
                          sx={{ mb: 2 }}
                        />
                      </Grid>
                    )}
                    <Grid item xs={12}>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => navigate(`/contracts/${contract.id}`)}
                      >
                        View Contract Details
                      </Button>
                    </Grid>
                  </Grid>
                </Box>
              ) : (
                <NoDataEmptyState
                  title="No contract associated"
                  description="This asset does not have an associated contract."
                  size="small"
                />
              )}
            </Paper>

            {/* Associated Dataset */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <StorageIcon />
                <Typography variant="h6">Associated Dataset</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {isLoadingDataset ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : datasetError ? (
                <Alert severity="error">
                  Failed to load dataset: {datasetError instanceof Error ? datasetError.message : 'Unknown error'}
                </Alert>
              ) : dataset ? (
                <Box>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="text.secondary">
                        Dataset ID
                      </Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                        {dataset.id}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="text.secondary">
                        Format
                      </Typography>
                      <Chip label={dataset.format} size="small" sx={{ mb: 2 }} />
                    </Grid>
                    {dataset.row_count !== null && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="body2" color="text.secondary">
                          Row Count
                        </Typography>
                        <Typography variant="body1" sx={{ mb: 2 }}>
                          {dataset.row_count.toLocaleString()}
                        </Typography>
                      </Grid>
                    )}
                    {dataset.version && (
                      <Grid item xs={12} sm={6}>
                        <Typography variant="body2" color="text.secondary">
                          Version
                        </Typography>
                        <Typography variant="body1" sx={{ mb: 2 }}>
                          {dataset.version}
                        </Typography>
                      </Grid>
                    )}
                    <Grid item xs={12}>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => navigate(`/datasets/${dataset.id}`)}
                      >
                        View Dataset Details
                      </Button>
                    </Grid>
                  </Grid>
                </Box>
              ) : (
                <NoDataEmptyState
                  title="No dataset associated"
                  description="This asset does not have an associated dataset."
                  size="small"
                />
              )}
            </Paper>
          </Grid>

          {/* Audit Log / History */}
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <HistoryIcon />
                <Typography variant="h6">History</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {isLoadingAudit ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : auditError ? (
                <Alert severity="error">
                  Failed to load audit log: {auditError instanceof Error ? auditError.message : 'Unknown error'}
                </Alert>
              ) : auditEvents && auditEvents.results.length > 0 ? (
                <Stack spacing={2}>
                  {auditEvents.results.slice(0, 10).map((event) => (
                    <Card key={event.id} variant="outlined">
                      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                        <Typography variant="body2" fontWeight={500}>
                          {event.action.replace(/_/g, ' ')}
                        </Typography>
                        {event.actor_user_name && (
                          <Typography variant="caption" color="text.secondary">
                            by {event.actor_user_name}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                          {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                  {auditEvents.count > 10 && (
                    <Button
                      variant="text"
                      size="small"
                      onClick={() => navigate(`/assets/${id}/history`)}
                    >
                      View All ({auditEvents.count} events)
                    </Button>
                  )}
                </Stack>
              ) : (
                <NoDataEmptyState
                  title="No history available"
                  description="No audit events found for this asset."
                  size="small"
                />
              )}
            </Paper>
          </Grid>
        </Grid>

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={deleteDialogOpen}
          onClose={() => !isDeleting && setDeleteDialogOpen(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Delete Asset</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete the asset &quot;{asset.name}&quot;? This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button
              onClick={handleDelete}
              color="error"
              variant="contained"
              disabled={isDeleting}
            >
              {isDeleting ? <CircularProgress size={20} /> : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

