/**
 * Marketplace Listing Card Component
 *
 * Card component for displaying marketplace listing information in a card layout.
 * Used in grid views and lists for contract discovery.
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  CardContent,
  CardHeader,
  CardActions,
  Typography,
  Box,
  Divider,
  Tooltip,
  Chip,
  Button,
} from '@mui/material'
import {
  Download as DownloadIcon,
  Visibility as VisibilityIcon,
  Star as StarIcon,
} from '@mui/icons-material'
import { formatDistanceToNow } from 'date-fns'
import type { MarketplaceListing, PricingModel } from '@/lib/api/marketplace'
import { useDownloadContract } from '@/hooks/useMarketplace'

/**
 * Get pricing model display text
 */
const getPricingModelText = (model: PricingModel): string => {
  switch (model) {
    case 'FREE':
      return 'Free'
    case 'FREE_AUTO_APPROVE':
      return 'Free (Auto-approve)'
    case 'REQUEST_APPROVAL':
      return 'Request Access'
    default:
      return model
  }
}

/**
 * Get pricing model color
 */
const getPricingModelColor = (model: PricingModel): 'default' | 'success' | 'info' | 'warning' => {
  switch (model) {
    case 'FREE':
    case 'FREE_AUTO_APPROVE':
      return 'success'
    case 'REQUEST_APPROVAL':
      return 'info'
    default:
      return 'default'
  }
}

export interface MarketplaceListingCardProps {
  /**
   * Marketplace listing data
   */
  listing: MarketplaceListing
  /**
   * Show full description or truncate
   * @default false
   */
  showFullDescription?: boolean
  /**
   * Show actions
   * @default true
   */
  showActions?: boolean
  /**
   * Show pricing info
   * @default true
   */
  showPricing?: boolean
  /**
   * Clickable card (navigates to detail page)
   * @default true
   */
  clickable?: boolean
  /**
   * Callback when card is clicked
   */
  onClick?: (listing: MarketplaceListing) => void
  /**
   * Callback when view is clicked
   */
  onView?: (listing: MarketplaceListing) => void
  /**
   * Callback when download is clicked
   */
  onDownload?: (listing: MarketplaceListing) => void
  /**
   * Whether this listing is featured
   * @default false
   */
  featured?: boolean
  /**
   * Additional card props
   */
  cardProps?: React.ComponentProps<typeof Card>
}

/**
 * Marketplace Listing Card Component
 *
 * @example
 * ```tsx
 * <MarketplaceListingCard
 *   listing={listing}
 *   onClick={(listing) => navigate(`/marketplace/${listing.id}`)}
 *   onDownload={(listing) => handleDownload(listing)}
 *   featured={true}
 * />
 * ```
 */
export const MarketplaceListingCard: React.FC<MarketplaceListingCardProps> = ({
  listing,
  showFullDescription = false,
  showActions = true,
  showPricing = true,
  clickable = true,
  onClick,
  onView,
  onDownload,
  featured = false,
  cardProps,
}) => {
  const navigate = useNavigate()
  const downloadContract = useDownloadContract({
    onSuccess: (data) => {
      // Create blob and trigger download
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
      console.error('Failed to download contract:', error)
    },
  })

  const handleClick = () => {
    if (clickable) {
      if (onClick) {
        onClick(listing)
      } else {
        navigate(`/marketplace/${listing.id}`)
      }
    }
  }

  const handleView = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (onView) {
      onView(listing)
    } else {
      navigate(`/marketplace/${listing.id}`)
    }
  }

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (onDownload) {
      onDownload(listing)
    } else {
      downloadContract.mutate({
        listingId: listing.id,
        format: 'original',
      })
    }
  }

  const title = listing.title || listing.metadata_json?.title || 'Untitled Listing'
  const description =
    listing.short_description ||
    listing.description ||
    listing.metadata_json?.short_description ||
    listing.metadata_json?.long_description ||
    'No description available'
  const truncatedDescription =
    !showFullDescription && description.length > 150
      ? `${description.substring(0, 150)}...`
      : description

  const tags = listing.tags || listing.metadata_json?.tags || []
  const domain = listing.domain || listing.metadata_json?.domain
  const priceAmount = listing.price_amount || listing.metadata_json?.price_amount
  const currency = listing.currency || listing.metadata_json?.currency || 'USD'

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: clickable ? 'pointer' : 'default',
        transition: 'transform 0.2s, box-shadow 0.2s',
        border: featured ? '2px solid' : 'none',
        borderColor: featured ? 'primary.main' : 'transparent',
        '&:hover': clickable
          ? {
              transform: 'translateY(-4px)',
              boxShadow: 4,
            }
          : {},
      }}
      onClick={handleClick}
      {...cardProps}
    >
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {featured && (
              <StarIcon sx={{ color: 'primary.main', fontSize: '1.2rem' }} />
            )}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="h6" component="div" noWrap>
                {title}
              </Typography>
              {listing.id && (
                <Typography variant="caption" color="text.secondary">
                  ID: {listing.id.substring(0, 8)}...
                </Typography>
              )}
            </Box>
          </Box>
        }
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={getPricingModelText(listing.pricing_model)}
              size="small"
              color={getPricingModelColor(listing.pricing_model)}
              variant="outlined"
            />
          </Box>
        }
      />
      <CardContent sx={{ flexGrow: 1 }}>
        {domain && (
          <Box sx={{ mb: 1 }}>
            <Chip
              label={domain}
              size="small"
              variant="outlined"
              sx={{ mb: 1 }}
            />
          </Box>
        )}

        {description && (
          <Tooltip title={showFullDescription ? undefined : description}>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                mb: 2,
                display: '-webkit-box',
                WebkitLineClamp: showFullDescription ? undefined : 3,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {truncatedDescription}
            </Typography>
          </Tooltip>
        )}

        {showPricing && priceAmount !== null && priceAmount !== undefined && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="h6" color="primary">
              {new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: currency,
              }).format(priceAmount)}
            </Typography>
          </Box>
        )}

        {tags.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
            {tags.slice(0, 5).map((tag, index) => (
              <Chip key={index} label={tag} size="small" variant="outlined" />
            ))}
            {tags.length > 5 && (
              <Chip label={`+${tags.length - 5}`} size="small" variant="outlined" />
            )}
          </Box>
        )}

        <Box sx={{ mt: 'auto', pt: 2 }}>
          <Divider sx={{ mb: 1 }} />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              {listing.published_at
                ? `Published ${formatDistanceToNow(new Date(listing.published_at), { addSuffix: true })}`
                : `Created ${formatDistanceToNow(new Date(listing.created_at), { addSuffix: true })}`}
            </Typography>
            {listing.status === 'PUBLISHED' && (
              <Chip
                label="Published"
                size="small"
                color="success"
                variant="outlined"
              />
            )}
          </Box>
        </Box>
      </CardContent>

      {showActions && (
        <CardActions sx={{ justifyContent: 'flex-end', px: 2, pb: 2 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size="small"
              startIcon={<VisibilityIcon />}
              onClick={handleView}
              variant="outlined"
            >
              View
            </Button>
            <Button
              size="small"
              startIcon={<DownloadIcon />}
              onClick={handleDownload}
              variant="contained"
              disabled={downloadContract.isPending}
            >
              {downloadContract.isPending ? 'Downloading...' : 'Download'}
            </Button>
          </Box>
        </CardActions>
      )}
    </Card>
  )
}

MarketplaceListingCard.displayName = 'MarketplaceListingCard'

