/**
 * ViolationCard Component
 *
 * Reusable card component for displaying individual compliance violations.
 * Shows violation type, severity, description, and remediation suggestions.
 */

import React from 'react'
import {
  Box,
  Typography,
  Chip,
  Card,
  CardContent,
  CardHeader,
  Divider,
  IconButton,
  Tooltip,
  Collapse,
} from '@mui/material'
import {
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material'
import type { ComplianceScanResults } from '@/lib/api/compliance'

export interface ViolationCardProps {
  /**
   * Violation data
   */
  violation: ComplianceScanResults['violations'][0]
  /**
   * Violation index (for key generation)
   */
  index?: number
  /**
   * Show full description by default
   * @default false
   */
  expanded?: boolean
  /**
   * Callback when card is clicked
   */
  onClick?: () => void
  /**
   * Show expand/collapse button
   * @default true
   */
  showExpand?: boolean
  /**
   * Custom card elevation
   * @default 1
   */
  elevation?: 1 | 2 | 4
}

/**
 * Get violation severity color
 */
function getSeverityColor(severity?: string): 'error' | 'warning' | 'info' | 'default' {
  if (!severity) return 'default'
  const upperSeverity = severity.toUpperCase()
  if (upperSeverity.includes('CRITICAL') || upperSeverity.includes('HIGH')) return 'error'
  if (upperSeverity.includes('MEDIUM') || upperSeverity.includes('WARN')) return 'warning'
  return 'info'
}

/**
 * Get violation severity icon
 */
function getSeverityIcon(severity?: string) {
  if (!severity) return <InfoIcon />
  const upperSeverity = severity.toUpperCase()
  if (upperSeverity.includes('CRITICAL') || upperSeverity.includes('HIGH')) return <ErrorIcon />
  if (upperSeverity.includes('MEDIUM') || upperSeverity.includes('WARN')) return <WarningIcon />
  return <InfoIcon />
}

/**
 * Get violation severity label
 */
function getSeverityLabel(severity?: string): string {
  if (!severity) return 'Unknown'
  const upperSeverity = severity.toUpperCase()
  if (upperSeverity.includes('CRITICAL')) return 'Critical'
  if (upperSeverity.includes('HIGH')) return 'High'
  if (upperSeverity.includes('MEDIUM')) return 'Medium'
  if (upperSeverity.includes('LOW')) return 'Low'
  if (upperSeverity.includes('INFO')) return 'Info'
  return severity
}

/**
 * ViolationCard Component
 *
 * @example
 * ```tsx
 * <ViolationCard
 *   violation={violation}
 *   expanded={false}
 *   showExpand={true}
 *   onClick={() => handleViolationClick(violation)}
 * />
 * ```
 */
export const ViolationCard: React.FC<ViolationCardProps> = ({
  violation,
  index,
  expanded: initialExpanded = false,
  onClick,
  showExpand = true,
  elevation = 1,
}) => {
  const [expanded, setExpanded] = React.useState(initialExpanded)

  const severity = violation.severity
  const severityColor = getSeverityColor(severity)
  const SeverityIcon = getSeverityIcon(severity)
  const severityLabel = getSeverityLabel(severity)

  const handleExpandClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setExpanded(!expanded)
  }

  return (
    <Card
      elevation={elevation}
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        transition: 'box-shadow 0.2s',
        '&:hover': onClick
          ? {
              boxShadow: 4,
            }
          : {},
      }}
      onClick={onClick}
    >
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <SeverityIcon color={severityColor} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, flex: 1 }}>
              {violation.type || 'Unknown Violation'}
            </Typography>
            <Chip
              label={severityLabel}
              size="small"
              color={severityColor}
              icon={<SeverityIcon />}
            />
            {violation.id && (
              <Chip
                label={`ID: ${violation.id.substring(0, 8)}`}
                size="small"
                variant="outlined"
                sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}
              />
            )}
            {showExpand && (
              <Tooltip title={expanded ? 'Collapse' : 'Expand'}>
                <IconButton size="small" onClick={handleExpandClick}>
                  {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Tooltip>
            )}
          </Box>
        }
        sx={{ pb: 1 }}
      />
      <Divider />
      <CardContent>
        {violation.description && (
          <Box sx={{ mb: expanded ? 2 : 0 }}>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                display: '-webkit-box',
                WebkitLineClamp: expanded ? undefined : 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {violation.description}
            </Typography>
          </Box>
        )}

        <Collapse in={expanded}>
          {violation.remediation && (
            <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                Remediation
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {violation.remediation}
              </Typography>
            </Box>
          )}

          {/* Additional violation details */}
          {Object.keys(violation).length > 4 && (
            <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                Additional Details
              </Typography>
              <Box component="dl" sx={{ m: 0 }}>
                {Object.entries(violation)
                  .filter(([key]) => !['id', 'type', 'severity', 'description', 'remediation'].includes(key))
                  .map(([key, value]) => (
                    <Box key={key} sx={{ mb: 1 }}>
                      <Typography component="dt" variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                        {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}:
                      </Typography>
                      <Typography component="dd" variant="body2" sx={{ ml: 2 }}>
                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                      </Typography>
                    </Box>
                  ))}
              </Box>
            </Box>
          )}
        </Collapse>
      </CardContent>
    </Card>
  )
}

ViolationCard.displayName = 'ViolationCard'

