/**
 * Dataset Detail Page
 *
 * Comprehensive dataset detail page with:
 * - Dataset information display
 * - Dataset schema display
 * - Dataset version history
 * - Data quality results
 * - Download action
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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  Storage as StorageIcon,
  History as HistoryIcon,
  Schema as SchemaIcon,
  Assessment as AssessmentIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import { useDataset } from '@/hooks/useDatasets'
import { useQuery } from '@tanstack/react-query'
import {
  getDatasetVersions,
  getFileDownloadUrl,
  type DatasetVersion,
} from '@/lib/api/datasets'
import { listAuditEvents } from '@/lib/api/audit'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { JSONViewer } from '@/components/data-display/JSONViewer'

/**
 * Dataset Detail Page Component
 */
export const DatasetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast } = useToastManager()

  // Download state
  const [isDownloading, setIsDownloading] = useState(false)

  // Fetch dataset data
  const {
    data: dataset,
    isLoading: isLoadingDataset,
    error: datasetError,
    refetch: refetchDataset,
  } = useDataset(id!)

  // Fetch dataset versions
  const {
    data: versions,
    isLoading: isLoadingVersions,
    error: versionsError,
  } = useQuery<DatasetVersion[], Error>({
    queryKey: ['dataset-versions', id],
    queryFn: () => getDatasetVersions(id!),
    enabled: !!id,
  })

  // Fetch audit events for this dataset
  const {
    data: auditEvents,
    isLoading: isLoadingAudit,
  } = useQuery({
    queryKey: ['audit-events', 'dataset', id],
    queryFn: () =>
      listAuditEvents({
        resource_type: 'DATASET',
        resource_id: id!,
        page_size: 50,
        ordering: '-created_at',
      }),
    enabled: !!id,
  })

  // Handle download
  const handleDownload = useCallback(async () => {
    if (!dataset || !dataset.file) {
      showToast({
        message: 'Dataset file not available',
        severity: 'error',
      })
      return
    }

    setIsDownloading(true)
    try {
      const downloadResponse = await getFileDownloadUrl(dataset.file)

      // Create a temporary anchor element to trigger download
      const link = document.createElement('a')
      link.href = downloadResponse.download_url
      link.download = downloadResponse.filename || `dataset-${dataset.id}.${dataset.format.toLowerCase()}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      showToast({
        message: 'Download started',
        severity: 'success',
      })
    } catch (error: any) {
      showToast({
        message: error.message || 'Failed to download dataset',
        severity: 'error',
      })
    } finally {
      setIsDownloading(false)
    }
  }, [dataset, showToast])

  // Get format color
  const getFormatColor = (format: string) => {
    switch (format) {
      case 'CSV':
        return 'primary'
      case 'JSON':
        return 'secondary'
      case 'PARQUET':
        return 'success'
      default:
        return 'default'
    }
  }

  // Loading state
  if (isLoadingDataset) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading dataset..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (datasetError || !dataset) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load dataset"
            message={datasetError?.message || 'Dataset not found'}
            onRetry={() => refetchDataset()}
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
            <IconButton onClick={() => navigate('/datasets')} aria-label="Back to datasets">
              <ArrowBackIcon />
            </IconButton>
            <Box>
              <Typography variant="h4" gutterBottom>
                Dataset {dataset.id.substring(0, 8)}...
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Version {dataset.version}
                {dataset.semantic_version && ` (${dataset.semantic_version})`}
                {dataset.is_current && ' • Current'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <IconButton onClick={() => refetchDataset()} aria-label="Refresh">
              <RefreshIcon />
            </IconButton>
            <Button
              variant="contained"
              startIcon={isDownloading ? <CircularProgress size={16} /> : <DownloadIcon />}
              onClick={handleDownload}
              disabled={isDownloading || !dataset.file}
            >
              {isDownloading ? 'Downloading...' : 'Download'}
            </Button>
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* Main Content */}
          <Grid item xs={12} md={8}>
            {/* Dataset Information */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <StorageIcon />
                <Typography variant="h6">Dataset Information</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Dataset ID
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2, fontFamily: 'monospace', fontSize: '0.875rem' }}>
                    {dataset.id}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Format
                  </Typography>
                  <Chip
                    label={dataset.format}
                    size="small"
                    color={getFormatColor(dataset.format) as any}
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Version
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 2 }}>
                    <Typography variant="body1">v{dataset.version}</Typography>
                    {dataset.is_current && (
                      <Chip label="Current" size="small" color="primary" />
                    )}
                    {dataset.semantic_version && (
                      <Chip
                        label={dataset.semantic_version}
                        size="small"
                        variant="outlined"
                        sx={{ fontFamily: 'monospace' }}
                      />
                    )}
                  </Box>
                </Grid>
                {dataset.version_tags && dataset.version_tags.length > 0 && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">
                      Version Tags
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                      {dataset.version_tags.map((tag, index) => (
                        <Chip key={index} label={tag} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Grid>
                )}
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Row Count
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {dataset.row_count !== null && dataset.row_count !== undefined
                      ? dataset.row_count.toLocaleString()
                      : 'N/A'}
                  </Typography>
                </Grid>
                {dataset.asset && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">
                      Associated Asset
                    </Typography>
                    <Button
                      variant="text"
                      size="small"
                      onClick={() => navigate(`/assets/${dataset.asset}`)}
                      sx={{ mb: 2, textTransform: 'none' }}
                    >
                      View Asset ({dataset.asset.substring(0, 8)}...)
                    </Button>
                  </Grid>
                )}
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Created
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {format(new Date(dataset.created_at), 'PPpp')}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatDistanceToNow(new Date(dataset.created_at), { addSuffix: true })})
                    </Typography>
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">
                    Last Updated
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {format(new Date(dataset.updated_at), 'PPpp')}
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      ({formatDistanceToNow(new Date(dataset.updated_at), { addSuffix: true })})
                    </Typography>
                  </Typography>
                </Grid>
              </Grid>
            </Paper>

            {/* Dataset Schema */}
            {dataset.schema_json && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <SchemaIcon />
                  <Typography variant="h6">Schema</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />

                {dataset.schema_json.fields && dataset.schema_json.fields.length > 0 ? (
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>Field Name</TableCell>
                          <TableCell>Type</TableCell>
                          <TableCell>Nullable</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {dataset.schema_json.fields.map((field, index) => (
                          <TableRow key={index}>
                            <TableCell>
                              <Typography variant="body2" fontWeight={500}>
                                {field.name}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              <Chip
                                label={field.type}
                                size="small"
                                variant="outlined"
                                sx={{ fontFamily: 'monospace' }}
                              />
                            </TableCell>
                            <TableCell>
                              {field.nullable ? (
                                <Chip label="Yes" size="small" color="warning" />
                              ) : (
                                <Chip label="No" size="small" color="success" />
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                ) : (
                  <NoDataEmptyState
                    title="No schema information"
                    description="Schema information is not available for this dataset."
                    size="small"
                  />
                )}
              </Paper>
            )}

            {/* Sample Data */}
            {dataset.sample_data_json && dataset.sample_data_json.length > 0 && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <StorageIcon />
                  <Typography variant="h6">Sample Data</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />
                <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                  <JSONViewer data={dataset.sample_data_json} />
                </Box>
              </Paper>
            )}

            {/* Data Quality Results */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <AssessmentIcon />
                <Typography variant="h6">Data Quality Results</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              <NoDataEmptyState
                title="No quality results available"
                description="Data quality checks have not been run for this dataset yet."
                size="small"
              />
            </Paper>
          </Grid>

          {/* Sidebar */}
          <Grid item xs={12} md={4}>
            {/* Version History */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <HistoryIcon />
                <Typography variant="h6">Version History</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {isLoadingVersions ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress size={24} />
                </Box>
              ) : versionsError ? (
                <Alert severity="error" sx={{ mb: 2 }}>
                  Failed to load versions
                </Alert>
              ) : versions && versions.length > 0 ? (
                <Stack spacing={2}>
                  {versions
                    .filter((v) => v.id !== dataset.id)
                    .slice(0, 10)
                    .map((version) => (
                      <Card key={version.id} variant="outlined">
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography variant="body2" fontWeight={500}>
                              Version {version.version}
                            </Typography>
                            {version.id === dataset.id && (
                              <Chip label="Current" size="small" color="primary" />
                            )}
                          </Box>
                          {version.semantic_version && (
                            <Chip
                              label={version.semantic_version}
                              size="small"
                              variant="outlined"
                              sx={{ mb: 1, fontFamily: 'monospace' }}
                            />
                          )}
                          {version.version_tags && version.version_tags.length > 0 && (
                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
                              {version.version_tags.map((tag, index) => (
                                <Chip key={index} label={tag} size="small" variant="outlined" />
                              ))}
                            </Box>
                          )}
                          <Typography variant="caption" color="text.secondary" display="block">
                            {formatDistanceToNow(new Date(version.created_at), { addSuffix: true })}
                          </Typography>
                          {version.id !== dataset.id && (
                            <Button
                              size="small"
                              variant="text"
                              onClick={() => navigate(`/datasets/${version.id}`)}
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
                  description="This is the only version of this dataset."
                  size="small"
                />
              )}
            </Paper>

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
                      onClick={() => navigate(`/datasets/${id}/history`)}
                    >
                      View All ({auditEvents.count} events)
                    </Button>
                  )}
                </Stack>
              ) : (
                <NoDataEmptyState
                  title="No history available"
                  description="No audit events found for this dataset."
                  size="small"
                />
              )}
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  )
}

