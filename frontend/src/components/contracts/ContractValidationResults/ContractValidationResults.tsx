/**
 * Contract Validation Results Component
 *
 * Displays contract validation results including errors, warnings, and status.
 */

import React from 'react'
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  Divider,
  Alert,
} from '@mui/material'
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Help as HelpIcon,
} from '@mui/icons-material'
import { Badge } from '@/components/data-display/Badge'
import type { ValidationStatus } from '@/lib/api/contracts'

export interface ValidationError {
  field?: string
  message: string
  code?: string
  [key: string]: any
}

export interface ValidationWarning {
  field?: string
  message: string
  severity?: 'low' | 'medium' | 'high'
  [key: string]: any
}

export interface ContractValidationResultsProps {
  /**
   * Validation status
   */
  validationStatus: ValidationStatus
  /**
   * List of validation errors
   */
  errors?: ValidationError[]
  /**
   * List of validation warnings
   */
  warnings?: ValidationWarning[]
  /**
   * Grouped errors by category
   */
  groupedErrors?: Record<string, ValidationError[]>
  /**
   * CLI version used for validation
   */
  cliVersion?: string
  /**
   * Validation timestamp
   */
  validatedAt?: string
  /**
   * Show summary
   * @default true
   */
  showSummary?: boolean
  /**
   * Show grouped errors
   * @default true
   */
  showGroupedErrors?: boolean
  /**
   * Compact mode (less spacing)
   * @default false
   */
  compact?: boolean
}

/**
 * Get validation status badge variant
 */
function getValidationStatusBadgeVariant(status: ValidationStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
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
 * Get validation status icon
 */
function getValidationStatusIcon(status: ValidationStatus): React.ReactElement {
  switch (status) {
    case 'VALID':
      return <CheckCircleIcon color="success" />
    case 'WARNING_ONLY':
      return <WarningIcon color="warning" />
    case 'INVALID':
    case 'ERROR':
      return <ErrorIcon color="error" />
    default:
      return <HelpIcon color="action" />
  }
}

/**
 * Contract Validation Results Component
 *
 * @example
 * ```tsx
 * <ContractValidationResults
 *   validationStatus="VALID"
 *   errors={[]}
 *   warnings={[]}
 * />
 * ```
 */
export const ContractValidationResults: React.FC<ContractValidationResultsProps> = ({
  validationStatus,
  errors = [],
  warnings = [],
  groupedErrors,
  cliVersion,
  validatedAt,
  showSummary = true,
  showGroupedErrors = true,
  compact = false,
}) => {
  const hasErrors = errors.length > 0
  const hasWarnings = warnings.length > 0
  const hasGroupedErrors = groupedErrors && Object.keys(groupedErrors).length > 0

  return (
    <Paper sx={{ p: compact ? 2 : 3 }}>
      {showSummary && (
        <Box sx={{ mb: compact ? 2 : 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            {getValidationStatusIcon(validationStatus)}
            <Badge variant={getValidationStatusBadgeVariant(validationStatus)} size="md">
              {validationStatus}
            </Badge>
            {(cliVersion || validatedAt) && (
              <Typography variant="caption" color="text.secondary">
                {cliVersion && `CLI v${cliVersion}`}
                {cliVersion && validatedAt && ' • '}
                {validatedAt && new Date(validatedAt).toLocaleString()}
              </Typography>
            )}
          </Box>

          {validationStatus === 'VALID' && !hasWarnings && (
            <Alert severity="success">
              Contract validation passed with no errors or warnings.
            </Alert>
          )}

          {validationStatus === 'VALID' && hasWarnings && (
            <Alert severity="warning">
              Contract validation passed but has {warnings.length} warning(s).
            </Alert>
          )}

          {validationStatus !== 'VALID' && (
            <Alert severity="error">
              Contract validation failed with {errors.length} error(s)
              {hasWarnings && ` and ${warnings.length} warning(s)`}.
            </Alert>
          )}
        </Box>
      )}

      {hasErrors && (
        <Box sx={{ mb: compact ? 2 : 3 }}>
          <Typography variant="subtitle2" color="error" gutterBottom>
            Errors ({errors.length})
          </Typography>
          <List dense={compact}>
            {errors.map((error, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  <ErrorIcon color="error" />
                </ListItemIcon>
                <ListItemText
                  primary={error.message}
                  secondary={
                    error.field
                      ? `Field: ${error.field}${error.code ? ` (${error.code})` : ''}`
                      : error.code
                      ? `Code: ${error.code}`
                      : undefined
                  }
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      {showGroupedErrors && hasGroupedErrors && groupedErrors && (
        <Box sx={{ mb: compact ? 2 : 3 }}>
          <Typography variant="subtitle2" color="error" gutterBottom>
            Grouped Errors
          </Typography>
          {Object.entries(groupedErrors).map(([category, categoryErrors]) => (
            <Box key={category} sx={{ mb: 2 }}>
              <Typography variant="body2" fontWeight="medium" gutterBottom>
                {category} ({categoryErrors.length})
              </Typography>
              <List dense={compact}>
                {categoryErrors.map((error, index) => (
                  <ListItem key={index}>
                    <ListItemIcon>
                      <ErrorIcon color="error" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={error.message}
                      secondary={error.field ? `Field: ${error.field}` : undefined}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          ))}
        </Box>
      )}

      {hasWarnings && (
        <Box>
          {hasErrors && <Divider sx={{ my: compact ? 2 : 3 }} />}
          <Typography variant="subtitle2" color="warning.main" gutterBottom>
            Warnings ({warnings.length})
          </Typography>
          <List dense={compact}>
            {warnings.map((warning, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  <WarningIcon color="warning" />
                </ListItemIcon>
                <ListItemText
                  primary={warning.message}
                  secondary={
                    warning.field
                      ? `Field: ${warning.field}${warning.severity ? ` (${warning.severity} severity)` : ''}`
                      : warning.severity
                      ? `Severity: ${warning.severity}`
                      : undefined
                  }
                />
              </ListItem>
            ))}
          </List>
        </Box>
      )}

      {!hasErrors && !hasWarnings && validationStatus === 'VALID' && (
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <CheckCircleIcon color="success" sx={{ fontSize: 48, mb: 1 }} />
          <Typography variant="body1" color="success.main">
            No errors or warnings found
          </Typography>
        </Box>
      )}
    </Paper>
  )
}

ContractValidationResults.displayName = 'ContractValidationResults'

