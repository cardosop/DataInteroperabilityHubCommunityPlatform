/**
 * Marketplace Asset Detail Page
 *
 * Comprehensive marketplace asset detail page with:
 * - Asset information display (name, description, domain, tags)
 * - Contract details (version, status, schema summary)
 * - Dataset information (version, size, format)
 * - Data quality metrics
 * - Compliance information
 * - Marketplace policy (license, intended use, restricted use)
 * - Contract download functionality
 * - Access request functionality
 * - Related assets display
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
  Alert,
  CircularProgress,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
} from '@mui/material'
import {
  ArrowBack as ArrowBackIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  RequestQuote as RequestQuoteIcon,
  Storage as StorageIcon,
  Description as DescriptionIcon,
  Assessment as AssessmentIcon,
  VerifiedUser as VerifiedUserIcon,
  Policy as PolicyIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
} from '@mui/icons-material'
import { formatDistanceToNow, format } from 'date-fns'
import {
  useMarketplaceListing,
  useMarketplaceListingPreview,
  useCreateMarketplaceOrder,
  useDownloadContract,
} from '@/hooks/useMarketplace'
import { useQuery } from '@tanstack/react-query'
import { searchMarketplaceContracts } from '@/lib/api/marketplace'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { DatasetSchemaViewer } from '@/components/datasets/DatasetSchemaViewer'
import { JSONViewer } from '@/components/data-display/JSONViewer'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { MarketplaceListingCard } from '@/components/marketplace'

/**
 * Format percentage for display
 */
const formatPercentage = (value: number): string => {
  return `${Math.round(value * 100)}%`
}

/**
 * Get quality score color
 */
const getQualityScoreColor = (score: number): 'success' | 'warning' | 'error' => {
  if (score >= 0.8) return 'success'
  if (score >= 0.6) return 'warning'
  return 'error'
}

/**
 * Get freshness color
 */
const getFreshnessColor = (freshness: string): 'success' | 'warning' | 'error' => {
  if (freshness === 'current') return 'success'
  if (freshness === 'stale') return 'warning'
  return 'error'
}

/**
 * Marketplace Asset Detail Page Component
 */
export const MarketplaceAssetDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { showToast } = useToastManager()

  // State
  const [accessRequestDialogOpen, setAccessRequestDialogOpen] = useState(false)

  // Fetch listing
  const {
    data: listing,
    isLoading: isLoadingListing,
    error: listingError,
    refetch: refetchListing,
  } = useMarketplaceListing(id)

  // Fetch preview (asset, dataset, quality metrics, schema)
  const {
    data: preview,
    isLoading: isLoadingPreview,
    error: previewError,
  } = useMarketplaceListingPreview(id)

  // Fetch related assets (similar listings in same domain)
  const {
    data: relatedListings,
    isLoading: isLoadingRelated,
  } = useQuery({
    queryKey: ['marketplace', 'related', listing?.domain],
    queryFn: () =>
      searchMarketplaceContracts({
        domain: listing?.domain || undefined,
        page_size: 6,
        access_mode: listing?.pricing_model,
      }),
    enabled: !!listing?.domain && !!listing?.pricing_model,
    select: (data) => ({
      ...data,
      results: data.results.filter((l) => l.id !== id).slice(0, 6),
    }),
  })

  // Download contract mutation
  const downloadContract = useDownloadContract({
    onSuccess: (data) => {
      // Create blob and download
      const blob = new Blob([data.contract_content], {
        type: data.format === 'JSON' ? 'application/json' : 'text/plain',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = data.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      showToast({
        message: 'Contract downloaded successfully',
        severity: 'success',
      })
    },
    onError: (error) => {
      showToast({
        message: `Failed to download contract: ${error.message}`,
        severity: 'error',
      })
    },
  })

  // Create order mutation
  const createOrder = useCreateMarketplaceOrder({
    onSuccess: (data) => {
      setAccessRequestDialogOpen(false)
      if (data.order.status === 'FULFILLED') {
        showToast({
          message: 'Access granted! You can now download and use this asset.',
          severity: 'success',
        })
      } else {
        showToast({
          message: 'Access request submitted. Waiting for approval.',
          severity: 'info',
        })
      }
      refetchListing()
    },
    onError: (error) => {
      showToast({
        message: `Failed to request access: ${error.message}`,
        severity: 'error',
      })
    },
  })

  // Handle download contract
  const handleDownloadContract = useCallback(() => {
    if (!id) return
    downloadContract.mutate({
      listingId: id,
      format: 'original',
    })
  }, [id, downloadContract])

  // Handle request access
  const handleRequestAccess = useCallback(() => {
    if (!id) return
    createOrder.mutate({
      listing_id: id,
    })
  }, [id, createOrder])

  // Handle confirm access request
  const handleConfirmAccessRequest = useCallback(() => {
    handleRequestAccess()
  }, [handleRequestAccess])

  // Loading state
  if (isLoadingListing) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading marketplace asset..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (listingError || !listing) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load marketplace asset"
            message={listingError?.message || 'Marketplace asset not found'}
            onRetry={() => refetchListing()}
          />
        </Box>
      </Container>
    )
  }

  const qualityMetrics = preview?.quality_metrics
  const schema = preview?.schema
  const sampleData = preview?.sample_data

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <IconButton onClick={() => navigate('/marketplace')} aria-label="Back to marketplace">
              <ArrowBackIcon />
            </IconButton>
            <Box>
              <Typography variant="h4" gutterBottom>
                {listing.title || 'Untitled Asset'}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center', mt: 1 }}>
                {listing.domain && (
                  <Chip label={listing.domain} size="small" variant="outlined" />
                )}
                {listing.tags && listing.tags.length > 0 && (
                  <>
                    {listing.tags.slice(0, 3).map((tag) => (
                      <Chip key={tag} label={tag} size="small" variant="outlined" />
                    ))}
                  </>
                )}
                <Chip
                  label={listing.pricing_model === 'FREE' ? 'Free' : listing.pricing_model === 'FREE_AUTO_APPROVE' ? 'Free (Auto-approve)' : 'Request Access'}
                  size="small"
                  color={listing.pricing_model === 'FREE' ? 'success' : 'primary'}
                />
              </Box>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <IconButton onClick={() => refetchListing()} aria-label="Refresh">
              <RefreshIcon />
            </IconButton>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={handleDownloadContract}
              disabled={downloadContract.isPending}
            >
              {downloadContract.isPending ? 'Downloading...' : 'Download Contract'}
            </Button>
            {listing.pricing_model !== 'FREE' && (
              <Button
                variant="contained"
                startIcon={<RequestQuoteIcon />}
                onClick={() => setAccessRequestDialogOpen(true)}
                disabled={createOrder.isPending}
              >
                {createOrder.isPending ? 'Requesting...' : 'Request Access'}
              </Button>
            )}
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* Main Content */}
          <Grid item xs={12} md={8}>
            {/* Asset Information */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <StorageIcon />
                <Typography variant="h6">Asset Information</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              <Grid container spacing={2}>
                {listing.title && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Title
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {listing.title}
                    </Typography>
                  </Grid>
                )}
                {listing.short_description && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Description
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {listing.short_description}
                    </Typography>
                  </Grid>
                )}
                {listing.long_description && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Detailed Description
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {listing.long_description}
                    </Typography>
                  </Grid>
                )}
                {listing.domain && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Domain
                    </Typography>
                    <Chip label={listing.domain} size="small" sx={{ mb: 2 }} />
                  </Grid>
                )}
                {listing.tags && listing.tags.length > 0 && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Tags
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                      {listing.tags.map((tag) => (
                        <Chip key={tag} label={tag} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </Grid>
                )}
                {listing.published_at && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Published
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {format(new Date(listing.published_at), 'PPpp')}
                      <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                        ({formatDistanceToNow(new Date(listing.published_at), { addSuffix: true })})
                      </Typography>
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </Paper>

            {/* Contract Details */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <DescriptionIcon />
                <Typography variant="h6">Contract Details</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Status
                  </Typography>
                  <Chip
                    label={listing.status}
                    color={listing.status === 'PUBLISHED' ? 'success' : 'default'}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Pricing Model
                  </Typography>
                  <Chip
                    label={
                      listing.pricing_model === 'FREE'
                        ? 'Free'
                        : listing.pricing_model === 'FREE_AUTO_APPROVE'
                        ? 'Free (Auto-approve)'
                        : 'Request Approval'
                    }
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </Grid>
                {schema && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Schema Summary
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {schema.fields.length} field{schema.fields.length !== 1 ? 's' : ''}
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </Paper>

            {/* Dataset Information */}
            {preview && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <StorageIcon />
                  <Typography variant="h6">Dataset Information</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />

                <Grid container spacing={2}>
                  {sampleData && (
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Total Rows
                      </Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                        {sampleData.total_rows.toLocaleString()}
                      </Typography>
                    </Grid>
                  )}
                  {schema && (
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Schema Fields
                      </Typography>
                      <Typography variant="body1" sx={{ mb: 2 }}>
                        {schema.fields.length}
                      </Typography>
                    </Grid>
                  )}
                </Grid>
              </Paper>
            )}

            {/* Data Quality Metrics */}
            {qualityMetrics && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <AssessmentIcon />
                  <Typography variant="h6">Data Quality Metrics</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />

                <Grid container spacing={3}>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Overall Score
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <LinearProgress
                        variant="determinate"
                        value={qualityMetrics.overall_score * 100}
                        color={getQualityScoreColor(qualityMetrics.overall_score)}
                        sx={{ flex: 1, height: 8, borderRadius: 4 }}
                      />
                      <Typography variant="h6" color={`${getQualityScoreColor(qualityMetrics.overall_score)}.main`}>
                        {formatPercentage(qualityMetrics.overall_score)}
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Completeness
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <LinearProgress
                        variant="determinate"
                        value={qualityMetrics.completeness * 100}
                        color={getQualityScoreColor(qualityMetrics.completeness)}
                        sx={{ flex: 1, height: 8, borderRadius: 4 }}
                      />
                      <Typography variant="body2">
                        {formatPercentage(qualityMetrics.completeness)}
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Accuracy
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <LinearProgress
                        variant="determinate"
                        value={qualityMetrics.accuracy * 100}
                        color={getQualityScoreColor(qualityMetrics.accuracy)}
                        sx={{ flex: 1, height: 8, borderRadius: 4 }}
                      />
                      <Typography variant="body2">
                        {formatPercentage(qualityMetrics.accuracy)}
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Freshness
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                      <Chip
                        label={qualityMetrics.freshness}
                        size="small"
                        color={getFreshnessColor(qualityMetrics.freshness)}
                        icon={
                          qualityMetrics.freshness === 'current' ? (
                            <CheckCircleIcon fontSize="small" />
                          ) : qualityMetrics.freshness === 'stale' ? (
                            <WarningIcon fontSize="small" />
                          ) : (
                            <ErrorIcon fontSize="small" />
                          )
                        }
                      />
                    </Box>
                  </Grid>
                </Grid>
              </Paper>
            )}

            {/* Schema Viewer */}
            {schema && (
              <Box sx={{ mb: 3 }}>
                <DatasetSchemaViewer schema={schema} title="Dataset Schema" />
              </Box>
            )}

            {/* Sample Data Preview */}
            {sampleData && sampleData.rows && sampleData.rows.length > 0 && (
              <Paper sx={{ p: 3, mb: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <StorageIcon />
                  <Typography variant="h6">Sample Data Preview</Typography>
                </Box>
                <Divider sx={{ my: 2 }} />
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Showing {sampleData.sample_size} of {sampleData.total_rows.toLocaleString()} rows
                </Typography>
                <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                  <JSONViewer data={sampleData.rows} />
                </Box>
              </Paper>
            )}
          </Grid>

          {/* Sidebar */}
          <Grid item xs={12} md={4}>
            {/* Marketplace Policy */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <PolicyIcon />
                <Typography variant="h6">Marketplace Policy</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              {listing.metadata_json?.license_summary && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    License
                  </Typography>
                  <Typography variant="body1">{listing.metadata_json.license_summary}</Typography>
                </Box>
              )}

              {listing.metadata_json?.intended_use && listing.metadata_json.intended_use.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Intended Use
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {listing.metadata_json.intended_use.map((use: string) => (
                      <Chip key={use} label={use} size="small" color="success" variant="outlined" />
                    ))}
                  </Box>
                </Box>
              )}

              {listing.metadata_json?.restricted_use && listing.metadata_json.restricted_use.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Restricted Use
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    {listing.metadata_json.restricted_use.map((use: string) => (
                      <Chip key={use} label={use} size="small" color="error" variant="outlined" />
                    ))}
                  </Box>
                </Box>
              )}
            </Paper>

            {/* Compliance Information */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <VerifiedUserIcon />
                <Typography variant="h6">Compliance Information</Typography>
              </Box>
              <Divider sx={{ my: 2 }} />

              <Alert severity="info" sx={{ mb: 2 }}>
                This asset has been published to the marketplace and is available for discovery and access.
              </Alert>

              {listing.pricing_model === 'REQUEST_APPROVAL' && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Access to this asset requires approval from the provider.
                </Alert>
              )}

              {listing.pricing_model === 'FREE_AUTO_APPROVE' && (
                <Alert severity="success" sx={{ mb: 2 }}>
                  Access to this asset is automatically approved upon request.
                </Alert>
              )}
            </Paper>

            {/* Provider Information */}
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Provider Information
              </Typography>
              <Divider sx={{ my: 2 }} />
              <Typography variant="body2" color="text.secondary">
                Published by tenant: {listing.tenant.substring(0, 8)}...
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        {/* Asset Ratings/Reviews */}
        {/* Note: Ratings/reviews API integration is pending.
            When available, this section will display:
            - Average rating (1-5 stars)
            - Total number of ratings
            - Recent reviews with user information
            - Ability to submit ratings/reviews (if user has access)
        */}
        <Paper sx={{ p: 3, mt: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <Typography variant="h6">Ratings & Reviews</Typography>
          </Box>
          <Divider sx={{ my: 2 }} />
          <Alert severity="info">
            Ratings and reviews feature is coming soon. This section will display user ratings and
            reviews for this asset once the feature is fully integrated.
          </Alert>
        </Paper>

        {/* Related Assets */}
        {relatedListings && relatedListings.results.length > 0 && (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h5" gutterBottom>
              Related Assets
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Similar assets you might be interested in
            </Typography>
            <Grid container spacing={3}>
              {relatedListings.results.map((relatedListing) => (
                <Grid item xs={12} sm={6} md={4} key={relatedListing.id}>
                  <MarketplaceListingCard
                    listing={relatedListing}
                    onClick={(listing) => navigate(`/marketplace/${listing.id}`)}
                  />
                </Grid>
              ))}
            </Grid>
          </Box>
        )}

        {/* Access Request Confirmation Dialog */}
        <Dialog
          open={accessRequestDialogOpen}
          onClose={() => setAccessRequestDialogOpen(false)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>Request Access</DialogTitle>
          <DialogContent>
            <DialogContentText>
              {listing.pricing_model === 'FREE_AUTO_APPROVE'
                ? 'Your access request will be automatically approved. You will be able to download and use this asset immediately.'
                : 'Your access request will be sent to the provider for approval. You will be notified once a decision is made.'}
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setAccessRequestDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={handleConfirmAccessRequest}
              variant="contained"
              disabled={createOrder.isPending}
            >
              {createOrder.isPending ? 'Requesting...' : 'Confirm Request'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

