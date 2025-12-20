/**
 * Dataset List Component
 *
 * List component for displaying multiple datasets in a grid or list layout.
 * Supports loading states, empty states, and error states.
 */

import React from 'react'
import { Grid, Box } from '@mui/material'
import type { Dataset } from '@/lib/api/datasets'
import { DatasetCard } from '../DatasetCard'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { CardSkeleton } from '@/components/loading/skeletons/CardSkeleton'

export interface DatasetListProps {
  /**
   * Datasets to display
   */
  datasets: Dataset[]
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
   * Callback when dataset is clicked
   */
  onDatasetClick?: (dataset: Dataset) => void
  /**
   * Callback when view is clicked
   */
  onView?: (dataset: Dataset) => void
  /**
   * Callback to retry on error
   */
  onRetry?: () => void
}

/**
 * Dataset List Component
 *
 * @example
 * ```tsx
 * <DatasetList
 *   datasets={datasets}
 *   loading={isLoading}
 *   error={error}
 *   onDatasetClick={(dataset) => navigate(`/datasets/${dataset.id}`)}
 *   onView={(dataset) => navigate(`/datasets/${dataset.id}`)}
 * />
 * ```
 */
export const DatasetList: React.FC<DatasetListProps> = ({
  datasets,
  loading = false,
  error = null,
  emptyMessage = 'No datasets found',
  emptyAction,
  variant = 'grid',
  columns = 3,
  spacing = 3,
  showActions = true,
  onDatasetClick,
  onView,
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
        title="Failed to load datasets"
        message={error.message || 'An error occurred while loading datasets.'}
        onRetry={onRetry}
      />
    )
  }

  // Empty state
  if (datasets.length === 0) {
    return (
      <NoDataEmptyState
        title={emptyMessage}
        description="Get started by uploading your first dataset."
        primaryAction={emptyAction}
      />
    )
  }

  // Grid layout
  if (variant === 'grid') {
    return (
      <Grid container spacing={spacing}>
        {datasets.map((dataset) => (
          <Grid item xs={12} sm={6} md={12 / columns} key={dataset.id}>
            <DatasetCard
              dataset={dataset}
              showActions={showActions}
              onClick={onDatasetClick}
              onView={onView}
            />
          </Grid>
        ))}
      </Grid>
    )
  }

  // List layout
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {datasets.map((dataset) => (
        <DatasetCard
          key={dataset.id}
          dataset={dataset}
          showActions={showActions}
          onClick={onDatasetClick}
          onView={onView}
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

DatasetList.displayName = 'DatasetList'

