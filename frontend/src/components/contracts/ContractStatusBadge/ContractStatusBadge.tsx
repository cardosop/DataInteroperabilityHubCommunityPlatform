/**
 * Contract Status Badge Component
 *
 * Displays contract status with appropriate color coding and icons.
 * Supports multiple status types: contract status, normalization status, and validation status.
 */

import React from 'react'
import { Chip, ChipProps } from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Help as HelpIcon,
  Edit as EditIcon,
  Archive as ArchiveIcon,
  Published as PublishedIcon,
} from '@mui/icons-material'
import type { ContractStatus, NormalizationStatus, ValidationStatus } from '@/lib/api/contracts'

export interface ContractStatusBadgeProps {
  /**
   * Status type to display
   */
  type: 'status' | 'normalization' | 'validation'
  /**
   * Status value
   */
  value: ContractStatus | NormalizationStatus | ValidationStatus
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
 * Get status color for contract status
 */
function getStatusColor(status: ContractStatus): ChipProps['color'] {
  switch (status) {
    case 'ACTIVE':
      return 'success'
    case 'DRAFT':
      return 'default'
    case 'RETIRED':
      return 'warning'
    default:
      return 'default'
  }
}

/**
 * Get status color for normalization status
 */
function getNormalizationStatusColor(status: NormalizationStatus): ChipProps['color'] {
  switch (status) {
    case 'NORMALIZED_OK':
      return 'success'
    case 'NORMALIZED_WITH_WARNINGS':
      return 'warning'
    case 'NORMALIZATION_FAILED':
      return 'error'
    case 'NOT_NORMALIZED':
      return 'default'
    default:
      return 'default'
  }
}

/**
 * Get status color for validation status
 */
function getValidationStatusColor(status: ValidationStatus): ChipProps['color'] {
  switch (status) {
    case 'VALID':
      return 'success'
    case 'WARNING_ONLY':
      return 'warning'
    case 'INVALID':
    case 'ERROR':
      return 'error'
    default:
      return 'default'
  }
}

/**
 * Get status icon
 */
function getStatusIcon(
  type: ContractStatusBadgeProps['type'],
  value: ContractStatusBadgeProps['value']
): React.ReactElement | null {
  if (type === 'status') {
    switch (value as ContractStatus) {
      case 'ACTIVE':
        return <CheckCircleIcon fontSize="small" />
      case 'DRAFT':
        return <EditIcon fontSize="small" />
      case 'RETIRED':
        return <ArchiveIcon fontSize="small" />
      default:
        return null
    }
  }

  if (type === 'normalization') {
    switch (value as NormalizationStatus) {
      case 'NORMALIZED_OK':
        return <CheckCircleIcon fontSize="small" />
      case 'NORMALIZED_WITH_WARNINGS':
        return <WarningIcon fontSize="small" />
      case 'NORMALIZATION_FAILED':
        return <ErrorIcon fontSize="small" />
      case 'NOT_NORMALIZED':
        return <HelpIcon fontSize="small" />
      default:
        return null
    }
  }

  if (type === 'validation') {
    switch (value as ValidationStatus) {
      case 'VALID':
        return <CheckCircleIcon fontSize="small" />
      case 'WARNING_ONLY':
        return <WarningIcon fontSize="small" />
      case 'INVALID':
      case 'ERROR':
        return <ErrorIcon fontSize="small" />
      default:
        return <HelpIcon fontSize="small" />
    }
  }

  return null
}

/**
 * Format status label for display
 */
function formatStatusLabel(
  type: ContractStatusBadgeProps['type'],
  value: ContractStatusBadgeProps['value']
): string {
  if (type === 'normalization') {
    return (value as NormalizationStatus).replace(/_/g, ' ')
  }
  return value as string
}

/**
 * Contract Status Badge Component
 *
 * @example
 * ```tsx
 * <ContractStatusBadge type="status" value="ACTIVE" />
 * <ContractStatusBadge type="normalization" value="NORMALIZED_OK" />
 * <ContractStatusBadge type="validation" value="VALID" />
 * ```
 */
export const ContractStatusBadge: React.FC<ContractStatusBadgeProps> = ({
  type,
  value,
  size = 'small',
  variant = 'outlined',
  showIcon = true,
  chipProps,
}) => {
  const getColor = (): ChipProps['color'] => {
    if (type === 'status') {
      return getStatusColor(value as ContractStatus)
    }
    if (type === 'normalization') {
      return getNormalizationStatusColor(value as NormalizationStatus)
    }
    if (type === 'validation') {
      return getValidationStatusColor(value as ValidationStatus)
    }
    return 'default'
  }

  const icon = showIcon ? getStatusIcon(type, value) : undefined
  const label = formatStatusLabel(type, value)

  return (
    <Chip
      icon={icon}
      label={label}
      size={size}
      variant={variant}
      color={getColor()}
      {...chipProps}
    />
  )
}

ContractStatusBadge.displayName = 'ContractStatusBadge'

