/**
 * Dataset Card Component
 *
 * Card component for displaying dataset information in a card layout.
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
  Chip,
  IconButton,
} from '@mui/material'
import {
  Visibility as VisibilityIcon,
  Storage as StorageIcon,
  Description as DescriptionIcon,
} from '@mui/icons-material'
import { formatDistanceToNow } from 'date-fns'
import type { Dataset, DatasetFormat } from '@/lib/api/datasets'

/**
 * Get format badge color
 */
const getFormatColor = (
  format: DatasetFormat
): 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' => {
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

/**
 * Format file size for display
 */
const formatFileSize = (bytes: number | null | undefined): string => {
  if (!bytes) return 'N/A'
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  if (bytes === 0) return '0 Bytes'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + ' ' + sizes[i]
}

export interface DatasetCardProps {
  /**
   * Dataset data
   */
  dataset: Dataset
  /**
   * Show actions
   * @default true
   */
  showActions?: boolean
  /**
   * Show related info (asset, schema info)
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
  onClick?: (dataset: Dataset) => void
  /**
   * Callback when view is clicked
   */
  onView?: (dataset: Dataset) => void
  /**
   * Additional card props
   */
  cardProps?: React.ComponentProps<typeof Card>
}

/**
 * Dataset Card Component
 *
 * @example
 * ```tsx
 * <DatasetCard
 *   dataset={dataset}
 *   onClick={(dataset) => navigate(`/datasets/${dataset.id}`)}
 *   onView={(dataset) => navigate(`/datasets/${dataset.id}`)}
 * />
 * ```
 */
const DatasetCardComponent: React.FC<DatasetCardProps> = ({
  dataset,
  showActions = true,
  showRelatedInfo = true,
  clickable = true,
  onClick,
  onView,
  cardProps,
}) => {
  const navigate = useNavigate()

  const handleClick = useCallback(() => {
    if (clickable) {
      if (onClick) {
        onClick(dataset)
      } else {
        navigate(`/datasets/${dataset.id}`)
      }
    }
  }, [clickable, onClick, dataset, navigate])

  const handleView = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    if (onView) {
      onView(dataset)
    } else {
      navigate(`/datasets/${dataset.id}`)
    }
  }, [onView, dataset, navigate])

  // Memoize computed values
  const schemaFieldCount = useMemo(
    () => dataset.schema_json?.fields?.length || 0,
    [dataset.schema_json?.fields?.length]
  )
  const rowCount = useMemo(() => dataset.row_count, [dataset.row_count])

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
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <StorageIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
              <Typography variant="h6" component="div" noWrap>
                Dataset v{dataset.version}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <Chip
                label={dataset.format}
                size="small"
                color={getFormatColor(dataset.format)}
                variant="outlined"
              />
              {dataset.is_current && (
                <Chip label="Current" size="small" color="primary" variant="outlined" />
              )}
              {dataset.semantic_version && (
                <Chip
                  label={dataset.semantic_version}
                  size="small"
                  variant="outlined"
                  sx={{ fontFamily: 'monospace' }}
                />
              )}
              {dataset.version_tags && dataset.version_tags.length > 0 && (
                <Tooltip title={dataset.version_tags.join(', ')}>
                  <Chip
                    label={`${dataset.version_tags.length} tag${dataset.version_tags.length !== 1 ? 's' : ''}`}
                    size="small"
                    variant="outlined"
                  />
                </Tooltip>
              )}
            </Box>
          </Box>
        }
      />
      <CardContent sx={{ flexGrow: 1 }}>
        {/* Schema Information */}
        {schemaFieldCount > 0 && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Schema
            </Typography>
            <Typography variant="body1" fontWeight={500}>
              {schemaFieldCount} field{schemaFieldCount !== 1 ? 's' : ''}
            </Typography>
          </Box>
        )}

        {/* Row Count */}
        {rowCount !== null && rowCount !== undefined && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Rows
            </Typography>
            <Typography variant="body1" fontWeight={500}>
              {rowCount.toLocaleString()}
            </Typography>
          </Box>
        )}

        {showRelatedInfo && (
          <Box sx={{ mt: 2 }}>
            <Divider sx={{ mb: 1 }} />
            <Box sx={{ display: 'flex', gap: 2, fontSize: '0.875rem', color: 'text.secondary' }}>
              {dataset.asset ? (
                <Tooltip title={dataset.asset}>
                  <Typography variant="caption" noWrap>
                    Asset: {dataset.asset.substring(0, 8)}...
                  </Typography>
                </Tooltip>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  No asset
                </Typography>
              )}
            </Box>
          </Box>
        )}

        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Created {formatDistanceToNow(new Date(dataset.created_at), { addSuffix: true })}
          </Typography>
        </Box>
      </CardContent>

      {showActions && (
        <CardActions sx={{ justifyContent: 'flex-end', px: 2, pb: 2 }}>
          <Tooltip title="View dataset">
            <IconButton
              size="small"
              onClick={handleView}
              aria-label={`View dataset ${dataset.id}`}
            >
              <VisibilityIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </CardActions>
      )}
    </Card>
  )
}

DatasetCardComponent.displayName = 'DatasetCard'

// Memoize DatasetCard to prevent unnecessary re-renders when parent re-renders
// Only re-render if dataset data or props change
export const DatasetCard = React.memo(DatasetCardComponent, (prevProps, nextProps) => {
  // Custom comparison: only re-render if dataset ID or key props change
  return (
    prevProps.dataset.id === nextProps.dataset.id &&
    prevProps.dataset.created_at === nextProps.dataset.created_at &&
    prevProps.dataset.format === nextProps.dataset.format &&
    prevProps.dataset.version === nextProps.dataset.version &&
    prevProps.clickable === nextProps.clickable &&
    prevProps.showActions === nextProps.showActions &&
    prevProps.showRelatedInfo === nextProps.showRelatedInfo &&
    prevProps.onClick === nextProps.onClick &&
    prevProps.onView === nextProps.onView
  )
})

