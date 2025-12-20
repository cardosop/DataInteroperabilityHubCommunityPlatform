/**
 * ProgressiveDisclosure Component
 *
 * Component for showing/hiding advanced fields.
 * Follows progressive disclosure pattern to reduce form complexity.
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Button,
  Collapse,
  Typography,
  Divider,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { spacing } from '@/styles/tokens'

export interface ProgressiveDisclosureProps {
  /**
   * Label for the disclosure toggle
   */
  label: string
  /**
   * Advanced content
   */
  children: React.ReactNode
  /**
   * Default expanded state
   */
  defaultExpanded?: boolean
  /**
   * Remember expanded state in localStorage
   */
  rememberState?: boolean
  /**
   * Storage key for remembering state
   */
  storageKey?: string
  /**
   * Show divider above disclosure
   */
  showDivider?: boolean
}

/**
 * ProgressiveDisclosure component for advanced fields
 */
export const ProgressiveDisclosure: React.FC<ProgressiveDisclosureProps> = ({
  label,
  children,
  defaultExpanded = false,
  rememberState = true,
  storageKey,
  showDivider = true,
}) => {
  const getStorageKey = () => {
    return storageKey || `progressive-disclosure-${label.toLowerCase().replace(/\s+/g, '-')}`
  }

  const getInitialState = (): boolean => {
    if (rememberState && typeof window !== 'undefined') {
      const stored = localStorage.getItem(getStorageKey())
      if (stored !== null) {
        return stored === 'true'
      }
    }
    return defaultExpanded
  }

  const [expanded, setExpanded] = useState(getInitialState)

  // Save state to localStorage when it changes
  useEffect(() => {
    if (rememberState && typeof window !== 'undefined') {
      localStorage.setItem(getStorageKey(), expanded.toString())
    }
  }, [expanded, rememberState, getStorageKey])

  const handleToggle = () => {
    setExpanded((prev) => !prev)
  }

  return (
    <Box>
      {showDivider && <Divider sx={{ marginY: spacing[3] }} />}
      <Button
        onClick={handleToggle}
        endIcon={expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        sx={{
          textTransform: 'none',
          justifyContent: 'space-between',
          width: '100%',
          padding: spacing[2],
          marginBottom: expanded ? spacing[2] : 0,
        }}
      >
        <Typography variant="body1" fontWeight={500}>
          {label}
        </Typography>
      </Button>
      <Collapse in={expanded}>
        <Box
          sx={{
            padding: spacing[3],
            backgroundColor: 'action.hover',
            borderRadius: 1,
            marginBottom: spacing[3],
          }}
        >
          {children}
        </Box>
      </Collapse>
    </Box>
  )
}

