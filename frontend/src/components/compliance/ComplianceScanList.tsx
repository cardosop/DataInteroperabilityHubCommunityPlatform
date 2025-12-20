/**
 * ComplianceScanList Component
 *
 * Reusable component for displaying compliance scans in a table format.
 * Supports filtering, sorting, pagination, and navigation.
 */

import React from 'react'
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  Typography,
} from '@mui/material'
import { ArrowForward as ArrowForwardIcon } from '@mui/icons-material'
import { useNavigate } from 'react-router-dom'
import type { ComplianceScan, ComplianceRunStatus, OverallComplianceStatus, RiskLevel } from '@/lib/api/compliance'
import { Badge } from '@/components/data-display/Badge'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { formatDistanceToNow } from 'date-fns'

export interface ComplianceScanListProps {
  /**
   * Compliance scans to display
   */
  scans: ComplianceScan[]
  /**
   * Total number of scans (for pagination)
   */
  totalCount?: number
  /**
   * Current page number
   * @default 1
   */
  page?: number
  /**
   * Total number of pages
   */
  totalPages?: number
  /**
   * Current page size
   * @default 20
   */
  pageSize?: number
  /**
   * Page size options
   * @default [10, 20, 50, 100]
   */
  pageSizeOptions?: number[]
  /**
   * Callback when page changes
   */
  onPageChange?: (page: number) => void
  /**
   * Callback when page size changes
   */
  onPageSizeChange?: (pageSize: number) => void
  /**
   * Callback when scan is clicked
   */
  onScanClick?: (scan: ComplianceScan) => void
  /**
   * Base URL for scan detail navigation
   * @default '/compliance/scans'
   */
  baseUrl?: string
  /**
   * Show pagination
   * @default true
   */
  showPagination?: boolean
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
}

/**
 * Get compliance status badge variant
 */
function getComplianceStatusBadgeVariant(
  status?: OverallComplianceStatus
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'PASS':
      return 'success'
    case 'WARN':
      return 'warning'
    case 'FAIL':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get risk level badge variant
 */
function getRiskLevelBadgeVariant(riskLevel?: RiskLevel): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!riskLevel) return 'neutral'
  switch (riskLevel) {
    case 'NONE':
    case 'LOW':
      return 'success'
    case 'MEDIUM':
      return 'warning'
    case 'HIGH':
    case 'CRITICAL':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get scan status badge variant
 */
function getScanStatusBadgeVariant(status: ComplianceRunStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (status) {
    case 'SUCCEEDED':
      return 'success'
    case 'RUNNING':
    case 'PENDING':
      return 'info'
    case 'FAILED':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

/**
 * ComplianceScanList Component
 *
 * @example
 * ```tsx
 * <ComplianceScanList
 *   scans={scans}
 *   totalCount={totalCount}
 *   page={page}
 *   totalPages={totalPages}
 *   onPageChange={setPage}
 *   onScanClick={(scan) => navigate(`/compliance/scans/${scan.id}`)}
 * />
 * ```
 */
export const ComplianceScanList: React.FC<ComplianceScanListProps> = ({
  scans,
  totalCount,
  page = 1,
  totalPages = 1,
  pageSize = 20,
  pageSizeOptions = [10, 20, 50, 100],
  onPageChange,
  onPageSizeChange,
  onScanClick,
  baseUrl = '/compliance/scans',
  showPagination = true,
  emptyMessage = 'No compliance scans found',
  emptyAction,
}) => {
  const navigate = useNavigate()

  const handleScanClick = (scan: ComplianceScan) => {
    if (onScanClick) {
      onScanClick(scan)
    } else {
      navigate(`${baseUrl}/${scan.id}`)
    }
  }

  // Empty state
  if (scans.length === 0) {
    return (
      <NoDataEmptyState
        title={emptyMessage}
        description="Run your first compliance scan to get started."
        primaryAction={emptyAction}
      />
    )
  }

  return (
    <Paper>
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Scan ID</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Compliance Status</TableCell>
              <TableCell>Risk Level</TableCell>
              <TableCell>Regulations</TableCell>
              <TableCell>Started</TableCell>
              <TableCell>Completed</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {scans.map((scan) => (
              <TableRow
                key={scan.id}
                sx={{ cursor: 'pointer' }}
                onClick={() => handleScanClick(scan)}
                hover
              >
                <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                  {scan.id.substring(0, 8)}...
                </TableCell>
                <TableCell>
                  <Badge variant={getScanStatusBadgeVariant(scan.status)} size="sm">
                    {scan.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  {scan.overall_status ? (
                    <Badge variant={getComplianceStatusBadgeVariant(scan.overall_status)} size="sm">
                      {scan.overall_status}
                    </Badge>
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell>
                  {scan.risk_level ? (
                    <Badge variant={getRiskLevelBadgeVariant(scan.risk_level)} size="sm">
                      {scan.risk_level}
                    </Badge>
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell>
                  {scan.regulations && scan.regulations.length > 0 ? (
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {scan.regulations.slice(0, 2).map((reg, idx) => (
                        <Chip key={idx} label={reg} size="small" />
                      ))}
                      {scan.regulations.length > 2 && (
                        <Chip label={`+${scan.regulations.length - 2}`} size="small" />
                      )}
                    </Box>
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell>{formatDate(scan.started_at)}</TableCell>
                <TableCell>{formatDate(scan.completed_at)}</TableCell>
                <TableCell align="right">
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleScanClick(scan)
                    }}
                  >
                    <ArrowForwardIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      {showPagination && totalPages > 1 && (
        <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
          <EnhancedPagination
            page={page}
            totalPages={totalPages}
            onPageChange={onPageChange || (() => {})}
            pageSize={pageSize}
            onPageSizeChange={onPageSizeChange || (() => {})}
            totalItems={totalCount || scans.length}
            pageSizeOptions={pageSizeOptions}
          />
        </Box>
      )}
    </Paper>
  )
}

ComplianceScanList.displayName = 'ComplianceScanList'

