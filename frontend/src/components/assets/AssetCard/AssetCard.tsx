/**
 * Asset Card Component
 *
 * Card component for displaying asset information in a card layout.
 * Used in grid views and lists.
 */

import React, { useCallback, useMemo } from 'react'
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
} from '@mui/material'
import { formatDistanceToNow } from 'date-fns'
import type { Asset } from '@/lib/api/assets'
import { AssetStatusBadge } from '../AssetStatusBadge'
import { AssetActions } from '../AssetActions'

export interface AssetCardProps {
  /**
   * Asset data
   */
  asset: Asset
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
   * Show contract/dataset info
   * @default true
   */
  showRelatedInfo?: boolean
  /**
   * Clickable card (navigates to detail page)
   * @default true
   */
  clickable?: boolean
  /**
   * Callback when card is clicked
   */
  onClick?: (asset: Asset) => void
  /**
   * Callback when view is clicked
   */
  onView?: (asset: Asset) => void
  /**
   * Callback when edit is clicked
   */
  onEdit?: (asset: Asset) => void
  /**
   * Callback when delete is clicked
   */
  onDelete?: (asset: Asset) => void
  /**
   * Additional card props
   */
  cardProps?: React.ComponentProps<typeof Card>
}

/**
 * Asset Card Component
 *
 * @example
 * ```tsx
 * <AssetCard
 *   asset={asset}
 *   onClick={(asset) => navigate(`/assets/${asset.id}`)}
 *   onEdit={(asset) => navigate(`/assets/${asset.id}/edit`)}
 *   onDelete={(asset) => handleDelete(asset)}
 * />
 * ```
 */
const AssetCardComponent: React.FC<AssetCardProps> = ({
  asset,
  showFullDescription = false,
  showActions = true,
  showRelatedInfo = true,
  clickable = true,
  onClick,
  onView,
  onEdit,
  onDelete,
  cardProps,
}) => {
  const navigate = useNavigate()

  const handleClick = useCallback(() => {
    if (clickable) {
      if (onClick) {
        onClick(asset)
      } else {
        navigate(`/assets/${asset.id}`)
      }
    }
  }, [clickable, onClick, asset, navigate])

  const handleView = useCallback((eOrAsset: React.MouseEvent | Asset) => {
    // Handle both event-based (from direct clicks) and asset-based (from AssetActions) calls
    const event = 'stopPropagation' in (eOrAsset as React.MouseEvent) ? (eOrAsset as React.MouseEvent) : null
    event?.stopPropagation?.()

    if (onView) {
      onView(asset)
    } else {
      navigate(`/assets/${asset.id}`)
    }
  }, [onView, asset, navigate])

  const handleEdit = useCallback((eOrAsset: React.MouseEvent | Asset) => {
    // Handle both event-based (from direct clicks) and asset-based (from AssetActions) calls
    const event = 'stopPropagation' in (eOrAsset as React.MouseEvent) ? (eOrAsset as React.MouseEvent) : null
    event?.stopPropagation?.()

    if (onEdit) {
      onEdit(asset)
    } else {
      navigate(`/assets/${asset.id}/edit`)
    }
  }, [onEdit, asset, navigate])

  const handleDelete = useCallback((eOrAsset: React.MouseEvent | Asset) => {
    // Handle both event-based (from direct clicks) and asset-based (from AssetActions) calls
    const event = 'stopPropagation' in (eOrAsset as React.MouseEvent) ? (eOrAsset as React.MouseEvent) : null
    event?.stopPropagation?.()

    onDelete?.(asset)
  }, [onDelete, asset])

  // Memoize description truncation
  const description = asset.description || 'No description'
  const truncatedDescription = useMemo(() => {
    return !showFullDescription && description.length > 150
      ? `${description.substring(0, 150)}...`
      : description
  }, [description, showFullDescription])

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: clickable ? 'pointer' : 'default',
        transition: 'transform 0.2s, box-shadow 0.2s',
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
          <Box>
            <Typography variant="h6" component="div" noWrap>
              {asset.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {asset.key}
            </Typography>
          </Box>
        }
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <AssetStatusBadge type="status" value={asset.status} size="small" />
          </Box>
        }
      />
      <CardContent sx={{ flexGrow: 1 }}>
        {asset.domain && (
          <Box sx={{ mb: 1 }}>
            <Typography variant="caption" color="text.secondary">
              Domain: {asset.domain}
            </Typography>
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

        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
          <AssetStatusBadge type="dq" value={asset.dq_status} size="small" />
          <AssetStatusBadge type="compliance" value={asset.compliance_status} size="small" />
          <AssetStatusBadge type="visibility" value={asset.visibility} size="small" />
        </Box>

        {showRelatedInfo && (
          <Box sx={{ mt: 2 }}>
            <Divider sx={{ mb: 1 }} />
            <Box sx={{ display: 'flex', gap: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
              {asset.contract_id && (
                <Typography variant="caption">
                  Contract: {asset.contract?.name || asset.contract_id.substring(0, 8)}
                </Typography>
              )}
              {asset.dataset_id && (
                <Typography variant="caption">
                  Dataset: {asset.dataset?.name || asset.dataset_id.substring(0, 8)}
                </Typography>
              )}
            </Box>
          </Box>
        )}

        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Updated {formatDistanceToNow(new Date(asset.updated_at), { addSuffix: true })}
          </Typography>
        </Box>
      </CardContent>

      {showActions && (
        <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <AssetActions
              asset={asset}
              variant="icon"
              size="small"
              showView={!!onView}
              showEdit={!!onEdit}
              showDelete={!!onDelete}
              onView={handleView}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          </Box>
        </CardActions>
      )}
    </Card>
  )
}

AssetCardComponent.displayName = 'AssetCard'

// Memoize AssetCard to prevent unnecessary re-renders when parent re-renders
// Only re-render if asset data or props change
export const AssetCard = React.memo(AssetCardComponent, (prevProps, nextProps) => {
  // Custom comparison: only re-render if asset ID or key props change
  return (
    prevProps.asset.id === nextProps.asset.id &&
    prevProps.asset.updated_at === nextProps.asset.updated_at &&
    prevProps.asset.status === nextProps.asset.status &&
    prevProps.clickable === nextProps.clickable &&
    prevProps.showActions === nextProps.showActions &&
    prevProps.showRelatedInfo === nextProps.showRelatedInfo &&
    prevProps.showFullDescription === nextProps.showFullDescription &&
    prevProps.onClick === nextProps.onClick &&
    prevProps.onView === nextProps.onView &&
    prevProps.onEdit === nextProps.onEdit &&
    prevProps.onDelete === nextProps.onDelete
  )
})

