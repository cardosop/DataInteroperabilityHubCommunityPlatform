/**
 * Contract Card Component
 *
 * Card component for displaying contract information in a card layout.
 * Used in grid views and lists.
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
} from '@mui/material'
import { formatDistanceToNow } from 'date-fns'
import type { Contract } from '@/lib/api/contracts'
import { ContractStatusBadge } from '../ContractStatusBadge'

/**
 * Get contract name from hub_contract_json
 */
const getContractName = (contract: Contract): string => {
  return (
    contract.hub_contract_json?.info?.name ||
    contract.hub_contract_json?.id ||
    'Unnamed Contract'
  )
}

/**
 * Get contract description from hub_contract_json
 */
const getContractDescription = (contract: Contract): string | null => {
  return contract.hub_contract_json?.info?.description || null
}

export interface ContractCardProps {
  /**
   * Contract data
   */
  contract: Contract
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
   * Show related info (asset, tags, owners)
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
  onClick?: (contract: Contract) => void
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
   * Additional card props
   */
  cardProps?: React.ComponentProps<typeof Card>
}

/**
 * Contract Card Component
 *
 * @example
 * ```tsx
 * <ContractCard
 *   contract={contract}
 *   onClick={(contract) => navigate(`/contracts/${contract.id}`)}
 *   onEdit={(contract) => navigate(`/contracts/${contract.id}/edit`)}
 *   onDelete={(contract) => handleDelete(contract)}
 * />
 * ```
 */
export const ContractCard: React.FC<ContractCardProps> = ({
  contract,
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

  const handleClick = () => {
    if (clickable) {
      if (onClick) {
        onClick(contract)
      } else {
        navigate(`/contracts/${contract.id}`)
      }
    }
  }

  const handleView = (e: React.MouseEvent) => {
    e?.stopPropagation?.()
    if (onView) {
      onView(contract)
    } else {
      navigate(`/contracts/${contract.id}`)
    }
  }

  const handleEdit = (e: React.MouseEvent) => {
    e?.stopPropagation?.()
    if (onEdit) {
      onEdit(contract)
    } else {
      navigate(`/contracts/${contract.id}/edit`)
    }
  }

  const handleDelete = (e: React.MouseEvent) => {
    e?.stopPropagation?.()
    onDelete?.(contract)
  }

  const contractName = getContractName(contract)
  const description = getContractDescription(contract) || 'No description'
  const truncatedDescription =
    !showFullDescription && description.length > 150
      ? `${description.substring(0, 150)}...`
      : description

  const tags = contract.tags || contract.hub_contract_json?.info?.tags || []
  const owners = contract.owners || contract.hub_contract_json?.info?.owners || []

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
              {contractName}
            </Typography>
            {contract.hub_contract_json?.id && (
              <Typography variant="caption" color="text.secondary">
                ID: {contract.hub_contract_json.id}
              </Typography>
            )}
          </Box>
        }
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <ContractStatusBadge type="status" value={contract.status} size="small" />
          </Box>
        }
      />
      <CardContent sx={{ flexGrow: 1 }}>
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
          <ContractStatusBadge type="normalization" value={contract.normalization_status} size="small" />
          {contract.validation_status && (
            <ContractStatusBadge type="validation" value={contract.validation_status} size="small" />
          )}
        </Box>

        {showRelatedInfo && (
          <Box sx={{ mt: 2 }}>
            <Divider sx={{ mb: 1 }} />
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {contract.asset_id && (
                <Typography variant="caption" color="text.secondary">
                  Asset: {contract.asset_id.substring(0, 8)}...
                </Typography>
              )}
              {tags.length > 0 && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {tags.slice(0, 3).map((tag, index) => (
                    <Chip key={index} label={tag} size="small" variant="outlined" />
                  ))}
                  {tags.length > 3 && (
                    <Chip label={`+${tags.length - 3}`} size="small" variant="outlined" />
                  )}
                </Box>
              )}
              {owners.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  Owners: {owners.map((o) => o.name || o.email).join(', ')}
                </Typography>
              )}
            </Box>
          </Box>
        )}

        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Updated {formatDistanceToNow(new Date(contract.updated_at), { addSuffix: true })}
          </Typography>
        </Box>
      </CardContent>

      {showActions && (
        <CardActions sx={{ justifyContent: 'flex-end', px: 2, pb: 2 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {onView && (
              <Tooltip title="View">
                <Chip
                  label="View"
                  size="small"
                  onClick={handleView}
                  sx={{ cursor: 'pointer' }}
                />
              </Tooltip>
            )}
            {onEdit && (
              <Tooltip title="Edit">
                <Chip
                  label="Edit"
                  size="small"
                  onClick={handleEdit}
                  sx={{ cursor: 'pointer' }}
                />
              </Tooltip>
            )}
            {onDelete && (
              <Tooltip title="Delete">
                <Chip
                  label="Delete"
                  size="small"
                  color="error"
                  onClick={handleDelete}
                  sx={{ cursor: 'pointer' }}
                />
              </Tooltip>
            )}
          </Box>
        </CardActions>
      )}
    </Card>
  )
}

ContractCard.displayName = 'ContractCard'

