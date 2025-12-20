/**
 * Sync Status Indicator Component
 *
 * Displays the status of offline action synchronization:
 * - Queued actions count
 * - Syncing state
 * - Sync errors
 */

import React from 'react'
import { Chip, Box, Tooltip } from '@mui/material'
import { Sync as SyncIcon, CheckCircle as CheckIcon, Error as ErrorIcon } from '@mui/icons-material'

export interface SyncError {
  actionId: string
  error: string
}

export interface SyncStatusIndicatorProps {
  /**
   * Number of queued actions
   */
  queuedCount: number
  /**
   * Whether sync is in progress
   */
  isSyncing: boolean
  /**
   * Sync errors
   */
  syncErrors?: SyncError[]
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * SyncStatusIndicator component
 */
export const SyncStatusIndicator: React.FC<SyncStatusIndicatorProps> = ({
  queuedCount,
  isSyncing,
  syncErrors = [],
  className,
}) => {
  // Don't render if no queued actions and not syncing
  if (queuedCount === 0 && !isSyncing && syncErrors.length === 0) {
    return null
  }

  const hasErrors = syncErrors.length > 0

  return (
    <Box className={className} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {isSyncing ? (
        <Tooltip title="Syncing offline actions...">
          <Chip
            icon={<SyncIcon />}
            label={`Syncing ${queuedCount} action${queuedCount !== 1 ? 's' : ''}...`}
            color="info"
            size="small"
            sx={{
              '& .MuiChip-icon': {
                animation: 'spin 2s linear infinite',
                '@keyframes spin': {
                  '0%': { transform: 'rotate(0deg)' },
                  '100%': { transform: 'rotate(360deg)' },
                },
              },
            }}
          />
        </Tooltip>
      ) : hasErrors ? (
        <Tooltip title={`${syncErrors.length} action(s) failed to sync`}>
          <Chip
            icon={<ErrorIcon />}
            label={`${syncErrors.length} failed, ${queuedCount} queued`}
            color="error"
            size="small"
          />
        </Tooltip>
      ) : queuedCount > 0 ? (
        <Tooltip title={`${queuedCount} action(s) waiting to sync when online`}>
          <Chip
            icon={<CheckIcon />}
            label={`${queuedCount} queued`}
            color="warning"
            size="small"
          />
        </Tooltip>
      ) : null}
    </Box>
  )
}

SyncStatusIndicator.displayName = 'SyncStatusIndicator'

