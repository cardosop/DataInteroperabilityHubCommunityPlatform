/**
 * Asset List Component
 *
 * List component for displaying multiple assets in a grid or list layout.
 * Supports loading states, empty states, and error states.
 */

import React from 'react'
import { Grid, Box, Typography } from '@mui/material'
import type { Asset } from '@/lib/api/assets'
import { AssetCard } from '../AssetCard'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { CardSkeleton } from '@/components/loading/skeletons/CardSkeleton'

export interface AssetListProps {
  /**
   * Assets to display
   */
  assets: Asset[]
  /**
   * Loading state
   * @default false
   */
  loading?: boolean
  /**
   * Error state
   */
  error?: Error | null
  /**
   * Empty state message
   */
  emptyMessage?: string
  /**
   * Empty state action
   */
  emptyAction?: {
    label: string
    onClick: () => void
  }
  /**
   * Layout variant
   * @default 'grid'
   */
  variant?: 'grid' | 'list'
  /**
   * Number of columns for grid layout
   * @default 3
   */
  columns?: number
  /**
   * Spacing between items
   * @default 3
   */
  spacing?: number
  /**
   * Show actions on cards
   * @default true
   */
  showActions?: boolean
  /**
   * Callback when asset is clicked
   */
  onAssetClick?: (asset: Asset) => void
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
   * Callback to retry on error
   */
  onRetry?: () => void
}

/**
 * Asset List Component
 *
 * @example
 * ```tsx
 * <AssetList
 *   assets={assets}
 *   loading={isLoading}
 *   error={error}
 *   onAssetClick={(asset) => navigate(`/assets/${asset.id}`)}
 *   onEdit={(asset) => navigate(`/assets/${asset.id}/edit`)}
 *   onDelete={(asset) => handleDelete(asset)}
 * />
 * ```
 */
export const AssetList: React.FC<AssetListProps> = ({
  assets,
  loading = false,
  error = null,
  emptyMessage = 'No assets found',
  emptyAction,
  variant = 'grid',
  columns = 3,
  spacing = 3,
  showActions = true,
  onAssetClick,
  onView,
  onEdit,
  onDelete,
  onRetry,
}) => {
  // Loading state
  if (loading) {
    return (
      <Grid container spacing={spacing}>
        {Array.from({ length: 6 }).map((_, index) => (
          <Grid item xs={12} sm={6} md={12 / columns} key={index}>
            <CardSkeleton showHeader showActions={showActions} />
          </Grid>
        ))}
      </Grid>
    )
  }

  // Error state
  if (error) {
    return (
      <ErrorState
        title="Failed to load assets"
        message={error.message || 'An error occurred while loading assets.'}
        onRetry={onRetry}
      />
    )
  }

  // Empty state
  if (assets.length === 0) {
    return (
      <NoDataEmptyState
        title={emptyMessage}
        description="Get started by creating your first asset."
        primaryAction={emptyAction}
      />
    )
  }

  // Grid layout
  if (variant === 'grid') {
    return (
      <Grid container spacing={spacing}>
        {assets.map((asset) => (
          <Grid item xs={12} sm={6} md={12 / columns} key={asset.id}>
            <AssetCard
              asset={asset}
              showActions={showActions}
              onClick={onAssetClick}
              onView={onView}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          </Grid>
        ))}
      </Grid>
    )
  }

  // List layout
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {assets.map((asset) => (
        <AssetCard
          key={asset.id}
          asset={asset}
          showActions={showActions}
          showFullDescription
          onClick={onAssetClick}
          onView={onView}
          onEdit={onEdit}
          onDelete={onDelete}
          cardProps={{
            sx: {
              width: '100%',
            },
          }}
        />
      ))}
    </Box>
  )
}

AssetList.displayName = 'AssetList'

