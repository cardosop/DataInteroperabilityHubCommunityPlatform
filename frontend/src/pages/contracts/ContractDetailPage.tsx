/**
 * Contract Detail Page
 *
 * Comprehensive contract detail page with:
 * - Contract information display
 * - Contract version history
 * - Validation results
 * - Associated assets
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
  Alert,
  CircularProgress,
  Stack,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material'
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  History as HistoryIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
  ExpandMore as ExpandMoreIcon,
  Description as DescriptionIcon,
  Verified as VerifiedIcon,
  Code as CodeIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import { useContract } from '@/hooks/useContract'
import { useContracts } from '@/hooks/useContracts'
import { useRealtimeContracts } from '@/hooks/useRealtimeContracts'
import { useDeleteContract, useValidateContract } from '@/hooks/useContractMutations'
import { useQuery } from '@tanstack/react-query'
import { listAssets } from '@/lib/api/assets'
import { listAuditEvents } from '@/lib/api/audit'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { JSONViewer } from '@/components/data-display/JSONViewer'

/**
 * Contract Detail Page Component
 */
export const ContractDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast } = useToastManager()

  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [validationExpanded, setValidationExpanded] = useState(false)

  // Fetch contract data
  const {
    data: contract,
    isLoading: isLoadingContract,
    error: contractError,
    refetch: refetchContract,
  } = useContract(id!)

  // Subscribe to real-time updates for this specific contract
  useRealtimeContracts({
    contractId: id || undefined,
    showNotifications: true,
    enabled: !!id,
  })

  // Fetch contract version history (all contracts for the same asset)
  // Note: We'll need to query contracts filtered by asset if the API supports it
  // For now, we'll show a placeholder or fetch all contracts and filter client-side
  const {
    data: versionHistory,
    isLoading: isLoadingHistory,
  } = useContracts(
    contract?.asset_id
      ? {
          page_size: 100,
          ordering: '-version',
        }
      : undefined,
    {
      enabled: !!contract?.asset_id,
    }
  )

  // Fetch associated assets (assets with this contract_id)
  const {
    data: associatedAssets,
    isLoading: isLoadingAssets,
  } = useQuery({
    queryKey: ['assets', 'contract', id],
    queryFn: () => listAssets({ page_size: 100 }),
    enabled: !!id,
    select: (data) => ({
      ...data,
      results: data.results.filter((asset) => asset.contract_id === id),
    }),
  })

  // Fetch validation results (from contract data or trigger validation)
  const validateContractMutation = useValidateContract({
    onSuccess: (data) => {
      showToast({
        message: `Validation ${data.validation_status.toLowerCase()}`,
        severity: data.validation_status === 'VALID' ? 'success' : 'warning',
      })
      setValidationExpanded(true)
      refetchContract()
    },
    onError: (error) => {
      showToast({
        message: error.message || 'Failed to validate contract',
        severity: 'error',
      })
    },
  })

  // Fetch audit events for this contract
  const {
    data: auditEvents,
    isLoading: isLoadingAudit,
  } = useQuery({
    queryKey: ['audit-events', 'contract', id],
    queryFn: () =>
      listAuditEvents({
        resource_type: 'CONTRACT',
        resource_id: id!,
        page_size: 50,
        ordering: '-created_at',
      }),
    enabled: !!id,
  })

  // Delete mutation
  const deleteContractMutation = useDeleteContract({
    onSuccess: () => {
      showToast({
        message: 'Contract deleted successfully',
        severity: 'success',
      })
      navigate('/contracts')
    },
    onError: (error) => {
      showToast({
        message: error.message || 'Failed to delete contract',
        severity: 'error',
      })
      setIsDeleting(false)
      setDeleteDialogOpen(false)
    },
  })

  // Handle delete
  const handleDelete = useCallback(async () => {
    if (!contract || !id) return

    setIsDeleting(true)
    try {
      await deleteContractMutation.mutateAsync(id)
    } catch (error) {
      // Error handled in onError callback
    }
  }, [contract, id, deleteContractMutation])

  // Handle edit navigation
  const handleEdit = useCallback(() => {
    if (!id) return
    navigate(`/contracts/${id}/edit`)
  }, [id, navigate])

  // Handle validate
  const handleValidate = useCallback(() => {
    if (!id) return
    validateContractMutation.mutate({ id })
  }, [id, validateContractMutation])

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'success'
      case 'DRAFT':
        return 'default'
      case 'RETIRED':
        return 'warning'
      default:
        return 'default'
    }
  }

  // Get normalization status color
  const getNormalizationStatusColor = (status: string) => {
    switch (status) {
      case 'NORMALIZED_OK':
        return 'success'
      case 'NORMALIZED_WITH_WARNINGS':
        return 'warning'
      case 'NORMALIZATION_FAILED':
        return 'error'
      default:
        return 'default'
    }
  }

  // Get validation status color
  const getValidationStatusColor = (status?: string) => {
    switch (status) {
      case 'VALID':
        return 'success'
      case 'INVALID':
        return 'error'
      case 'WARNING_ONLY':
        return 'warning'
      case 'ERROR':
        return 'error'
      default:
        return 'default'
    }
  }

  // Get validation status icon
  const getValidationStatusIcon = (status?: string) => {
    switch (status) {
      case 'VALID':
        return <CheckCircleIcon fontSize="small" />
      case 'INVALID':
      case 'ERROR':
        return <ErrorIcon fontSize="small" />
      case 'WARNING_ONLY':
        return <WarningIcon fontSize="small" />
      default:
        return <HelpIcon fontSize="small" />
    }
  }

  // Loading state
  if (isLoadingContract) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading contract..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (contractError || !contract) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load contract"
            message={contractError?.message || 'Contract not found'}
            onRetry={() => refetchContract()}
          />
        </Box>
      </Container>
    )
  }

  const contractName = contract.hub_contract_json?.info?.name || contract.id
  const contractVersion = contract.hub_contract_version || contract.original_spec_version

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={() => navigate('/contracts')} aria-label="Back to contracts">
              <ArrowBackIcon />
            </IconButton>
            <Box>
              <Typography variant="h4" gutterBottom>
                {contractName}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Contract ID: {contract.id}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <IconButton onClick={() => refetchContract()} aria-label="Refresh">
              <RefreshIcon />
            </IconButton>
            <Button
              variant="outlined"
              startIcon={<VerifiedIcon />}
              onClick={handleValidate}
              disabled={validateContractMutation.isPending}
            >
              {validateContractMutation.isPending ? 'Validating...' : 'Validate'}
            </Button>
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
          {/* Contract Information */}
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Contract Information
              </Typography>
              <Divider sx={{ my: 2 }} />

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Contract Name
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {contractName}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Status
                  </Typography>
                  <Chip
                    label={contract.status}
                    color={getStatusColor(contract.status) as any}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Version
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {contract.version}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Hub Contract Version
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {contractVersion || 'N/A'}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Original Spec Type
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {contract.original_spec_type}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Original Spec Version
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {contract.original_spec_version}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Original Format
                  </Typography>
                  <Chip label={contract.original_format || 'N/A'} size="small" sx={{ mb: 2 }} />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Normalization Status
                  </Typography>
                  <Chip
                    label={contract.normalization_status || 'NOT_NORMALIZED'}
                    color={getNormalizationStatusColor(contract.normalization_status || 'NOT_NORMALIZED') as any}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                {contract.validation_status && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">
                      Validation Status
                    </Typography>
                    <Chip
                      icon={getValidationStatusIcon(contract.validation_status)}
                      label={contract.validation_status}
                      color={getValidationStatusColor(contract.validation_status) as any}
                      size="small"
                      sx={{ mb: 2 }}
                    />
                  </Grid>
                )}
                {contract.asset_id && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">
                      Associated Asset
                    </Typography>
                    <Button
                      variant="text"
                      size="small"
                      onClick={() => navigate(`/assets/${contract.asset_id}`)}
                      sx={{ mb: 2, textTransform: 'none' }}
                    >
                      View Asset ({contract.asset_id.substring(0, 8)}...)
                    </Button>
                  </Grid>
                )}
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Created
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {format(new Date(contract.created_at), 'PPpp')}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatDistanceToNow(new Date(contract.created_at), { addSuffix: true })})
                    </Typography>
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Last Updated
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {format(new Date(contract.updated_at), 'PPpp')}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatDistanceToNow(new Date(contract.updated_at), { addSuffix: true })})
                    </Typography>
                  </Typography>
                </Grid>
              </Grid>
            </Paper>

            {/* Contract JSON */}
            {contract.hub_contract_json && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <CodeIcon />
                  <Typography variant="h6">Contract JSON</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />
                <Box sx={{ maxHeight: 600, overflow: 'auto' }}>
                  <JSONViewer data={contract.hub_contract_json} />
                </Box>
              </Paper>
            )}

            {/* Validation Results */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <VerifiedIcon />
                <Typography variant="h6">Validation Results</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {contract.validation_status ? (
                <Box>
                  <Alert
                    severity={
                      contract.validation_status === 'VALID'
                        ? 'success'
                        : contract.validation_status === 'WARNING_ONLY'
                        ? 'warning'
                        : 'error'
                    }
                    icon={getValidationStatusIcon(contract.validation_status)}
                    sx={{ mb: 2 }}
                  >
                    <Typography variant="body1" fontWeight={500}>
                      Validation Status: {contract.validation_status}
                    </Typography>
                  </Alert>

                  {contract.validation_errors && contract.validation_errors.length > 0 && (
                    <Accordion expanded={validationExpanded} onChange={(e, expanded) => setValidationExpanded(expanded)}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2">
                          Errors ({contract.validation_errors.length})
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Stack spacing={1}>
                          {contract.validation_errors.map((error: any, index: number) => (
                            <Alert key={index} severity="error">
                              {typeof error === 'string' ? error : error.message || JSON.stringify(error)}
                            </Alert>
                          ))}
                        </Stack>
                      </AccordionDetails>
                    </Accordion>
                  )}

                  {contract.validation_warnings && contract.validation_warnings.length > 0 && (
                    <Accordion sx={{ mt: 1 }}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2">
                          Warnings ({contract.validation_warnings.length})
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Stack spacing={1}>
                          {contract.validation_warnings.map((warning: any, index: number) => (
                            <Alert key={index} severity="warning">
                              {typeof warning === 'string' ? warning : warning.message || JSON.stringify(warning)}
                            </Alert>
                          ))}
                        </Stack>
                      </AccordionDetails>
                    </Accordion>
                  )}
                </Box>
              ) : (
                <NoDataEmptyState
                  title="No validation results"
                  description="Click 'Validate' to run validation on this contract."
                  size="small"
                />
              )}
            </Paper>

            {/* Associated Assets */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <DescriptionIcon />
                <Typography variant="h6">Associated Assets</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {isLoadingAssets ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : associatedAssets && associatedAssets.results.length > 0 ? (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Name</TableCell>
                        <TableCell>Key</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {associatedAssets.results.map((asset) => (
                        <TableRow key={asset.id}>
                          <TableCell>{asset.name}</TableCell>
                          <TableCell>{asset.key}</TableCell>
                          <TableCell>
                            <Chip
                              label={asset.status}
                              size="small"
                              color={asset.status === 'ACTIVE' ? 'success' : 'default'}
                            />
                          </TableCell>
                          <TableCell>
                            <Button
                              size="small"
                              onClick={() => navigate(`/assets/${asset.id}`)}
                            >
                              View
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <NoDataEmptyState
                  title="No associated assets"
                  description="This contract is not associated with any assets."
                  size="small"
                />
              )}
            </Paper>
          </Grid>

          {/* Sidebar */}
          <Grid item xs={12} md={4}>
            {/* Version History */}
            {contract.asset_id && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <HistoryIcon />
                  <Typography variant="h6">Version History</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />

                {isLoadingHistory ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress size={24} />
                  </Box>
                ) : versionHistory && versionHistory.results.length > 0 ? (
                  <Stack spacing={2}>
                    {versionHistory.results
                      .filter((c) => c.asset_id === contract.asset_id && c.id !== contract.id)
                      .slice(0, 10)
                      .map((version) => (
                        <Card key={version.id} variant="outlined">
                          <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                              <Typography variant="body2" fontWeight={500}>
                                Version {version.version}
                              </Typography>
                              {version.id === contract.id && (
                                <Chip label="Current" size="small" color="primary" />
                              )}
                            </Box>
                            <Chip
                              label={version.status}
                              size="small"
                              color={getStatusColor(version.status) as any}
                              sx={{ mb: 1 }}
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              {formatDistanceToNow(new Date(version.created_at), { addSuffix: true })}
                            </Typography>
                            {version.id !== contract.id && (
                              <Button
                                size="small"
                                variant="text"
                                onClick={() => navigate(`/contracts/${version.id}`)}
                                sx={{ mt: 1 }}
                              >
                                View
                              </Button>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                  </Stack>
                ) : (
                  <NoDataEmptyState
                    title="No version history"
                    description="This is the only version of this contract."
                    size="small"
                  />
                )}
              </Paper>
            )}

            {/* Audit Log / History */}
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
                      onClick={() => navigate(`/contracts/${id}/history`)}
                    >
                      View All ({auditEvents.count} events)
                    </Button>
                  )}
                </Stack>
              ) : (
                <NoDataEmptyState
                  title="No history available"
                  description="No audit events found for this contract."
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
          <DialogTitle>Delete Contract</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete the contract &quot;{contractName}&quot;? This action cannot be undone.
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

