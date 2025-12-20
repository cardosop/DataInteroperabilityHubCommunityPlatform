/**
 * ValidationPanel Component
 *
 * Panel displaying validation and normalization status with:
 * - Real-time validation status
 * - Error list (expandable, clickable to navigate to field)
 * - Warning list (expandable, clickable to navigate to field)
 * - Validation summary (error count, warning count)
 * - Auto-scroll to first error
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Chip,
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  NavigateNext as NavigateNextIcon,
} from '@mui/icons-material'
import { Badge } from '@/components/data-display/Badge'
import type { ValidationError, ValidationWarning, ValidationStatus } from './types'

export interface ValidationPanelProps {
  validationStatus?: ValidationStatus
  errors: ValidationError[]
  warnings: ValidationWarning[]
  onNavigateToField?: (field?: string) => void
  autoScrollToFirstError?: boolean
}

/**
 * ValidationPanel component
 */
export const ValidationPanel: React.FC<ValidationPanelProps> = ({
  validationStatus,
  errors,
  warnings,
  onNavigateToField,
  autoScrollToFirstError = true,
}) => {
  const [errorsExpanded, setErrorsExpanded] = useState(false)
  const [warningsExpanded, setWarningsExpanded] = useState(false)
  const firstErrorRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to first error
  useEffect(() => {
    if (autoScrollToFirstError && errors.length > 0 && firstErrorRef.current) {
      firstErrorRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [errors.length, autoScrollToFirstError])

  const handleErrorClick = (error: ValidationError) => {
    if (onNavigateToField && error.field) {
      onNavigateToField(error.field)
    }
  }

  const handleWarningClick = (warning: ValidationWarning) => {
    if (onNavigateToField && warning.field) {
      onNavigateToField(warning.field)
    }
  }

  const getValidationStatusBadge = () => {
    if (!validationStatus) {
      return (
        <Badge variant="neutral" size="sm">
          Not Validated
        </Badge>
      )
    }

    switch (validationStatus) {
      case 'VALID':
        return (
          <Badge variant="success" size="sm">
            Valid
          </Badge>
        )
      case 'WARNING_ONLY':
        return (
          <Badge variant="warning" size="sm">
            Warnings Only
          </Badge>
        )
      case 'INVALID':
      case 'ERROR':
        return (
          <Badge variant="error" size="sm">
            Invalid
          </Badge>
        )
      default:
        return (
          <Badge variant="neutral" size="sm">
            {validationStatus}
          </Badge>
        )
    }
  }

  return (
    <Box
      sx={{
        borderTop: '1px solid',
        borderColor: 'divider',
        backgroundColor: 'background.paper',
        padding: 2,
      }}
    >
      {/* Validation Status Summary */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
          Validation Status:
        </Typography>
        {getValidationStatusBadge()}
        {errors.length > 0 && (
          <Chip
            icon={<ErrorIcon />}
            label={`${errors.length} Error${errors.length !== 1 ? 's' : ''}`}
            color="error"
            size="small"
          />
        )}
        {warnings.length > 0 && (
          <Chip
            icon={<WarningIcon />}
            label={`${warnings.length} Warning${warnings.length !== 1 ? 's' : ''}`}
            color="warning"
            size="small"
          />
        )}
      </Box>

      {/* Errors Accordion */}
      {errors.length > 0 && (
        <Accordion
          expanded={errorsExpanded}
          onChange={(_, expanded) => setErrorsExpanded(expanded)}
          sx={{ mb: 1 }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <ErrorIcon color="error" />
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                Errors ({errors.length})
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <List dense>
              {errors.map((error, index) => (
                <ListItem
                  key={index}
                  ref={index === 0 ? firstErrorRef : undefined}
                  sx={{
                    cursor: error.field ? 'pointer' : 'default',
                    '&:hover': error.field
                      ? {
                          backgroundColor: 'action.hover',
                        }
                      : {},
                  }}
                  onClick={() => handleErrorClick(error)}
                  secondaryAction={
                    error.field ? (
                      <IconButton edge="end" size="small">
                        <NavigateNextIcon />
                      </IconButton>
                    ) : undefined
                  }
                >
                  <ListItemText
                    primary={error.message}
                    secondary={error.field ? `Field: ${error.field}` : error.code}
                  />
                </ListItem>
              ))}
            </List>
          </AccordionDetails>
        </Accordion>
      )}

      {/* Warnings Accordion */}
      {warnings.length > 0 && (
        <Accordion
          expanded={warningsExpanded}
          onChange={(_, expanded) => setWarningsExpanded(expanded)}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <WarningIcon color="warning" />
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                Warnings ({warnings.length})
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <List dense>
              {warnings.map((warning, index) => (
                <ListItem
                  key={index}
                  sx={{
                    cursor: warning.field ? 'pointer' : 'default',
                    '&:hover': warning.field
                      ? {
                          backgroundColor: 'action.hover',
                        }
                      : {},
                  }}
                  onClick={() => handleWarningClick(warning)}
                  secondaryAction={
                    warning.field ? (
                      <IconButton edge="end" size="small">
                        <NavigateNextIcon />
                      </IconButton>
                    ) : undefined
                  }
                >
                  <ListItemText
                    primary={warning.message}
                    secondary={
                      warning.field
                        ? `Field: ${warning.field}${warning.severity ? ` • ${warning.severity}` : ''}`
                        : warning.severity
                    }
                  />
                </ListItem>
              ))}
            </List>
          </AccordionDetails>
        </Accordion>
      )}

      {/* No Errors/Warnings Message */}
      {errors.length === 0 && warnings.length === 0 && validationStatus === 'VALID' && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            color: 'success.main',
            padding: 2,
          }}
        >
          <CheckCircleIcon />
          <Typography variant="body2">No validation errors or warnings</Typography>
        </Box>
      )}
    </Box>
  )
}

ValidationPanel.displayName = 'ValidationPanel'

