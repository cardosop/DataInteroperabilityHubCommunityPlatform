/**
 * Asset Status Badge Component
 *
 * Displays asset status with appropriate color coding and icons.
 * Supports multiple status types: asset status, data quality status, and compliance status.
 */

import React from 'react'
import { Chip, ChipProps } from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
  Public as PublicIcon,
  Lock as LockIcon,
  Edit as EditIcon,
  Archive as ArchiveIcon,
} from '@mui/icons-material'
import type { AssetStatus, DQStatus, ComplianceStatus, AssetVisibility } from '@/lib/api/assets'

export interface AssetStatusBadgeProps {
  /**
   * Status type to display
   */
  type: 'status' | 'dq' | 'compliance' | 'visibility'
  /**
   * Status value
   */
  value: AssetStatus | DQStatus | ComplianceStatus | AssetVisibility
  /**
   * Size of the badge
   * @default 'small'
   */
  size?: 'small' | 'medium'
  /**
   * Variant of the badge
   * @default 'outlined'
   */
  variant?: 'filled' | 'outlined'
  /**
   * Show icon
   * @default true
   */
  showIcon?: boolean
  /**
   * Additional Chip props
   */
  chipProps?: Partial<ChipProps>
}

/**
 * Get status color for asset status
 */
function getStatusColor(status: AssetStatus): ChipProps['color'] {
  switch (status) {
    case 'ACTIVE':
      return 'success'
    case 'PUBLIC':
      return 'info'
    case 'DRAFT':
      return 'default'
    case 'RETIRED':
      return 'warning'
    default:
      return 'default'
  }
}

/**
 * Get status color for DQ/compliance status
 */
function getQualityStatusColor(status: DQStatus | ComplianceStatus): ChipProps['color'] {
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    default:
      return 'default'
  }
}

/**
 * Get status icon
 */
function getStatusIcon(
  type: AssetStatusBadgeProps['type'],
  value: AssetStatusBadgeProps['value']
): React.ReactElement | null {
  if (type === 'status') {
    switch (value as AssetStatus) {
      case 'ACTIVE':
        return <CheckCircleIcon fontSize="small" />
      case 'PUBLIC':
        return <PublicIcon fontSize="small" />
      case 'DRAFT':
        return <EditIcon fontSize="small" />
      case 'RETIRED':
        return <ArchiveIcon fontSize="small" />
      default:
        return null
    }
  }

  if (type === 'visibility') {
    switch (value as AssetVisibility) {
      case 'PUBLIC':
        return <PublicIcon fontSize="small" />
      case 'INTERNAL':
        return <LockIcon fontSize="small" />
      default:
        return null
    }
  }

  if (type === 'dq' || type === 'compliance') {
    switch (value as DQStatus | ComplianceStatus) {
      case 'PASS':
        return <CheckCircleIcon fontSize="small" />
      case 'WARN':
        return <WarningIcon fontSize="small" />
      case 'FAIL':
        return <ErrorIcon fontSize="small" />
      default:
        return <HelpIcon fontSize="small" />
    }
  }

  return null
}

/**
 * Asset Status Badge Component
 *
 * @example
 * ```tsx
 * <AssetStatusBadge type="status" value="ACTIVE" />
 * <AssetStatusBadge type="dq" value="PASS" />
 * <AssetStatusBadge type="compliance" value="WARN" />
 * ```
 */
export const AssetStatusBadge: React.FC<AssetStatusBadgeProps> = ({
  type,
  value,
  size = 'small',
  variant = 'outlined',
  showIcon = true,
  chipProps,
}) => {
  const getColor = (): ChipProps['color'] => {
    if (type === 'status') {
      return getStatusColor(value as AssetStatus)
    }
    if (type === 'dq' || type === 'compliance') {
      return getQualityStatusColor(value as DQStatus | ComplianceStatus)
    }
    if (type === 'visibility') {
      return (value as AssetVisibility) === 'PUBLIC' ? 'primary' : 'default'
    }
    return 'default'
  }

  const icon = showIcon ? getStatusIcon(type, value) : undefined

  return (
    <Chip
      icon={icon}
      label={value}
      size={size}
      variant={variant}
      color={getColor()}
      {...chipProps}
    />
  )
}

AssetStatusBadge.displayName = 'AssetStatusBadge'

