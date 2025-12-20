/**
 * FormSection Component
 *
 * Component for grouping related form fields into sections.
 * Supports accordion-style collapsible sections.
 */

import React, { useState } from 'react'
import {
  Paper,
  Typography,
  Box,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { spacing } from '@/styles/tokens'

export interface FormSectionProps {
  /**
   * Section title
   */
  title: string
  /**
   * Section description (optional)
   */
  description?: string
  /**
   * Section content
   */
  children: React.ReactNode
  /**
   * Collapsible section (accordion style)
   */
  collapsible?: boolean
  /**
   * Default expanded state (for collapsible sections)
   */
  defaultExpanded?: boolean
  /**
   * Section variant
   */
  variant?: 'default' | 'outlined' | 'elevated'
}

/**
 * FormSection component for grouping form fields
 */
export const FormSection: React.FC<FormSectionProps> = ({
  title,
  description,
  children,
  collapsible = false,
  defaultExpanded = true,
  variant = 'default',
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (collapsible) {
    return (
      <Accordion
        expanded={expanded}
        onChange={(_, isExpanded) => setExpanded(isExpanded)}
        sx={{ marginBottom: spacing[3] }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box>
            <Typography variant="h6">{title}</Typography>
            {description && (
              <Typography variant="body2" color="text.secondary">
                {description}
              </Typography>
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ paddingTop: spacing[2] }}>{children}</Box>
        </AccordionDetails>
      </Accordion>
    )
  }

  return (
    <Paper
      variant={variant === 'outlined' ? 'outlined' : 'elevation'}
      elevation={variant === 'elevated' ? 2 : 0}
      sx={{
        padding: spacing[4],
        marginBottom: spacing[4],
      }}
    >
      <Box sx={{ marginBottom: spacing[3] }}>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        {description && (
          <Typography variant="body2" color="text.secondary">
            {description}
          </Typography>
        )}
        <Divider sx={{ marginTop: spacing[2] }} />
      </Box>
      <Box>{children}</Box>
    </Paper>
  )
}

