/**
 * ContractDetailModal Component
 *
 * Modal component for displaying contract details with preview.
 * Shows full contract information, preview, and action buttons (download, request access).
 */

import React, { useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Tabs,
  Tab,
  IconButton,
  CircularProgress,
  Alert,
} from '@mui/material'
import {
  Close as CloseIcon,
  Download as DownloadIcon,
  RequestQuote as RequestAccessIcon,
  Visibility as PreviewIcon,
} from '@mui/icons-material'
import { ContractPreview } from '@/components/contracts/ContractPreview'
import { useContract } from '@/hooks/useContract'
import { useAsset } from '@/hooks/useAssets'
import { useDownloadContract } from '@/hooks/useMarketplace'
import type { MarketplaceListing } from '@/lib/api/marketplace'
import { contractToHubContract } from './utils'

export interface ContractDetailModalProps {
  open: boolean
  listing: MarketplaceListing | null
  onClose: () => void
  onRequestAccess?: (listing: MarketplaceListing) => void
}

/**
 * ContractDetailModal component
 */
export const ContractDetailModal: React.FC<ContractDetailModalProps> = ({
  open,
  listing,
  onClose,
  onRequestAccess,
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'preview'>('details')

  // Get asset first, then get contract from asset
  const { data: asset, isLoading: isLoadingAsset } = useAsset(
    listing?.asset || null,
    { enabled: !!listing?.asset && open }
  )

  // Get contract from asset's contract_id
  const contractId = asset?.contract_id || undefined
  const { data: contract, isLoading: isLoadingContract, error: contractError } = useContract(
    contractId || '',
    { enabled: !!contractId && open }
  )

  // Download hook
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
    },
    onError: (error) => {
      console.error('Download failed:', error)
    },
  })

  const handleDownload = () => {
    if (!listing) return
    downloadContract.mutate({
      listingId: listing.id,
      format: 'original',
    })
  }

  const handleRequestAccess = () => {
    if (!listing || !onRequestAccess) return
    onRequestAccess(listing)
  }

  const handleClose = () => {
    setActiveTab('details')
    onClose()
  }

  if (!listing) return null

  // Convert listing to HubContract for preview (if we have contract data)
  const hubContract = contract ? contractToHubContract(contract) : null

  const title = listing.title || listing.metadata_json?.title || 'Contract Details'
  const description =
    listing.long_description ||
    listing.description ||
    listing.metadata_json?.long_description ||
    listing.short_description ||
    listing.metadata_json?.short_description ||
    'No description available'

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="xl"
      fullWidth
      PaperProps={{
        sx: {
          height: '90vh',
          maxHeight: '90vh',
        },
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6" component="div" sx={{ flex: 1 }}>
            {title}
          </Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
            <Tab label="Details" value="details" />
            {hubContract && <Tab label="Preview" value="preview" />}
          </Tabs>
        </Box>

        {/* Tab Content */}
        <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
          {activeTab === 'details' && (
            <Box>
              {/* Description */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
                  Description
                </Typography>
                <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                  {description}
                </Typography>
              </Box>

              {/* Metadata */}
              <Box sx={{ mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                  Information
                </Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                  {listing.domain && (
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Domain
                      </Typography>
                      <Typography variant="body1">{listing.domain}</Typography>
                    </Box>
                  )}
                  {listing.pricing_model && (
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Access Mode
                      </Typography>
                      <Typography variant="body1">
                        {listing.pricing_model === 'FREE'
                          ? 'Free'
                          : listing.pricing_model === 'FREE_AUTO_APPROVE'
                          ? 'Free (Auto-approve)'
                          : 'Request Access'}
                      </Typography>
                    </Box>
                  )}
                  {listing.price_amount !== null && listing.price_amount !== undefined && (
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Price
                      </Typography>
                      <Typography variant="body1">
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: listing.currency || 'USD',
                        }).format(listing.price_amount)}
                      </Typography>
                    </Box>
                  )}
                  {listing.published_at && (
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Published
                      </Typography>
                      <Typography variant="body1">
                        {new Date(listing.published_at).toLocaleDateString()}
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Box>

              {/* Tags */}
              {listing.tags && listing.tags.length > 0 && (
                <Box sx={{ mb: 3 }}>
                  <Typography variant="h6" sx={{ mb: 1, fontWeight: 600 }}>
                    Tags
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {listing.tags.map((tag, index) => (
                      <Typography
                        key={index}
                        variant="body2"
                        sx={{
                          px: 1.5,
                          py: 0.5,
                          bgcolor: 'primary.light',
                          color: 'primary.contrastText',
                          borderRadius: 1,
                        }}
                      >
                        {tag}
                      </Typography>
                    ))}
                  </Box>
                </Box>
              )}

              {/* Contract Loading/Error */}
              {(isLoadingAsset || isLoadingContract) && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress />
                </Box>
              )}
              {contractError && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  Could not load full contract details: {contractError.message}
                </Alert>
              )}
              {!isLoadingAsset && !isLoadingContract && !contract && asset && !asset.contract_id && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  This asset does not have an associated contract.
                </Alert>
              )}
            </Box>
          )}

          {activeTab === 'preview' && (
            <Box>
              {hubContract ? (
                <ContractPreview contract={hubContract} />
              ) : (
                <Alert severity="info">
                  Contract preview is not available. Please use the Details tab to view contract information.
                </Alert>
              )}
            </Box>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose}>Close</Button>
        {listing.pricing_model === 'REQUEST_APPROVAL' && onRequestAccess && (
          <Button
            variant="contained"
            startIcon={<RequestAccessIcon />}
            onClick={handleRequestAccess}
          >
            Request Access
          </Button>
        )}
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={handleDownload}
          disabled={downloadContract.isPending}
        >
          {downloadContract.isPending ? 'Downloading...' : 'Download Contract'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

ContractDetailModal.displayName = 'ContractDetailModal'

