/**
 * Contract List Component
 *
 * List component for displaying multiple contracts in a grid or list layout.
 * Supports loading states, empty states, and error states.
 */

import React from 'react'
import { Grid, Box } from '@mui/material'
import type { Contract } from '@/lib/api/contracts'
import { ContractCard } from '../ContractCard'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { CardSkeleton } from '@/components/loading/skeletons/CardSkeleton'

export interface ContractListProps {
  /**
   * Contracts to display
   */
  contracts: Contract[]
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
   * Callback when contract is clicked
   */
  onContractClick?: (contract: Contract) => void
  /**
   * Callback when view is clicked
   */
  onView?: (contract: Contract) => void
  /**
   * Callback when edit is clicked
   */
  onEdit?: (contract: Contract) => void
  /**
   * Callback when delete is clicked
   */
  onDelete?: (contract: Contract) => void
  /**
   * Callback to retry on error
   */
  onRetry?: () => void
}

/**
 * Contract List Component
 *
 * @example
 * ```tsx
 * <ContractList
 *   contracts={contracts}
 *   loading={isLoading}
 *   error={error}
 *   onContractClick={(contract) => navigate(`/contracts/${contract.id}`)}
 *   onEdit={(contract) => navigate(`/contracts/${contract.id}/edit`)}
 *   onDelete={(contract) => handleDelete(contract)}
 * />
 * ```
 */
export const ContractList: React.FC<ContractListProps> = ({
  contracts,
  loading = false,
  error = null,
  emptyMessage = 'No contracts found',
  emptyAction,
  variant = 'grid',
  columns = 3,
  spacing = 3,
  showActions = true,
  onContractClick,
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
        title="Failed to load contracts"
        message={error.message || 'An error occurred while loading contracts.'}
        onRetry={onRetry}
      />
    )
  }

  // Empty state
  if (contracts.length === 0) {
    return (
      <NoDataEmptyState
        title={emptyMessage}
        description="Get started by creating your first contract."
        primaryAction={emptyAction}
      />
    )
  }

  // Grid layout
  if (variant === 'grid') {
    return (
      <Grid container spacing={spacing}>
        {contracts.map((contract) => (
          <Grid item xs={12} sm={6} md={12 / columns} key={contract.id}>
            <ContractCard
              contract={contract}
              showActions={showActions}
              onClick={onContractClick}
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
      {contracts.map((contract) => (
        <ContractCard
          key={contract.id}
          contract={contract}
          showActions={showActions}
          showFullDescription
          onClick={onContractClick}
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

ContractList.displayName = 'ContractList'

