/**
 * EditorHeader Component
 *
 * Header component for contract editor displaying:
 * - Contract metadata (name, description, version)
 * - Normalization status badge
 * - Validation status badge
 * - Action buttons (Save, Validate, Activate)
 * - Sticky header on scroll
 */

import React from 'react'
import {
  Box,
  Typography,
  Button,
  Tooltip,
  IconButton,
} from '@mui/material'
import {
  Save as SaveIcon,
  CheckCircle as ValidateIcon,
  PlayArrow as ActivateIcon,
  Cancel as CancelIcon,
  Undo as UndoIcon,
  Redo as RedoIcon,
  Visibility as PreviewIcon,
} from '@mui/icons-material'
import { Badge } from '@/components/data-display/Badge'
import type {
  NormalizationStatus,
  ValidationStatus,
} from './types'

export interface EditorHeaderProps {
  contractName?: string
  contractDescription?: string
  contractVersion?: string
  normalizationStatus?: NormalizationStatus
  validationStatus?: ValidationStatus
  isDirty: boolean
  isSaving: boolean
  isValidating: boolean
  canUndo?: boolean
  canRedo?: boolean
  onSave: () => void
  onValidate: () => void
  onActivate?: () => void
  onCancel: () => void
  onUndo?: () => void
  onRedo?: () => void
  onPreview?: () => void
}

/**
 * Get normalization status badge variant
 */
function getNormalizationStatusBadgeVariant(
  status?: NormalizationStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'NORMALIZED_OK':
      return 'success'
    case 'NORMALIZED_WITH_WARNINGS':
      return 'warning'
    case 'NORMALIZATION_FAILED':
      return 'error'
    case 'NOT_NORMALIZED':
      return 'neutral'
    default:
      return 'neutral'
  }
}

/**
 * Get validation status badge variant
 */
function getValidationStatusBadgeVariant(
  status?: ValidationStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'VALID':
      return 'success'
    case 'WARNING_ONLY':
      return 'warning'
    case 'INVALID':
    case 'ERROR':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Format normalization status for display
 */
function formatNormalizationStatus(status?: NormalizationStatus): string {
  if (!status) return 'Not Normalized'
  return status.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

/**
 * Format validation status for display
 */
function formatValidationStatus(status?: ValidationStatus): string {
  if (!status) return 'Not Validated'
  return status.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
}

/**
 * EditorHeader component
 */
export const EditorHeader: React.FC<EditorHeaderProps> = ({
  contractName,
  contractDescription,
  contractVersion,
  normalizationStatus,
  validationStatus,
  isDirty,
  isSaving,
  isValidating,
  canUndo = false,
  canRedo = false,
  onSave,
  onValidate,
  onActivate,
  onCancel,
  onUndo,
  onRedo,
  onPreview,
}) => {
  return (
    <Box
      sx={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        backgroundColor: 'white',
        borderBottom: '1px solid',
        borderColor: 'divider',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        padding: 2,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: 2,
        }}
      >
        {/* Left: Contract Metadata */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <Typography
              variant="h5"
              sx={{
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {contractName || 'Untitled Contract'}
            </Typography>
            {contractVersion && (
              <Typography variant="body2" color="text.secondary">
                v{contractVersion}
              </Typography>
            )}
          </Box>
          {contractDescription && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
              }}
            >
              {contractDescription}
            </Typography>
          )}
        </Box>

        {/* Center: Status Badges */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Tooltip title={`Normalization: ${formatNormalizationStatus(normalizationStatus)}`}>
            <Box>
              <Badge
                variant={getNormalizationStatusBadgeVariant(normalizationStatus)}
                size="sm"
              >
                {formatNormalizationStatus(normalizationStatus)}
              </Badge>
            </Box>
          </Tooltip>
          <Tooltip title={`Validation: ${formatValidationStatus(validationStatus)}`}>
            <Box>
              <Badge
                variant={getValidationStatusBadgeVariant(validationStatus)}
                size="sm"
              >
                {formatValidationStatus(validationStatus)}
              </Badge>
            </Box>
          </Tooltip>
        </Box>

        {/* Right: Action Buttons */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {/* Undo/Redo */}
          {onUndo && (
            <Tooltip title="Undo (Ctrl+Z)">
              <IconButton
                onClick={onUndo}
                disabled={!canUndo || isSaving || isValidating}
                size="small"
              >
                <UndoIcon />
              </IconButton>
            </Tooltip>
          )}
          {onRedo && (
            <Tooltip title="Redo (Ctrl+Y)">
              <IconButton
                onClick={onRedo}
                disabled={!canRedo || isSaving || isValidating}
                size="small"
              >
                <RedoIcon />
              </IconButton>
            </Tooltip>
          )}
          {onUndo || onRedo ? <Box sx={{ width: 1, borderLeft: 1, borderColor: 'divider', mx: 1, height: 24 }} /> : null}

          {/* Preview */}
          {onPreview && (
            <Button
              variant="outlined"
              startIcon={<PreviewIcon />}
              onClick={onPreview}
              disabled={isSaving || isValidating}
            >
              Preview
            </Button>
          )}

          <Button
            variant="outlined"
            startIcon={<CancelIcon />}
            onClick={onCancel}
            disabled={isSaving || isValidating}
          >
            Cancel
          </Button>
          <Button
            variant="outlined"
            startIcon={<ValidateIcon />}
            onClick={onValidate}
            disabled={isSaving || isValidating}
          >
            {isValidating ? 'Validating...' : 'Validate'}
          </Button>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={onSave}
            disabled={isSaving || isValidating || !isDirty}
          >
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
          {onActivate && (
            <Button
              variant="contained"
              color="success"
              startIcon={<ActivateIcon />}
              onClick={onActivate}
              disabled={isSaving || isValidating || !validationStatus || validationStatus !== 'VALID'}
            >
              Activate
            </Button>
          )}
        </Box>
      </Box>
    </Box>
  )
}

EditorHeader.displayName = 'EditorHeader'

