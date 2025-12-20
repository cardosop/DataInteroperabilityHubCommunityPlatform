/**
 * SearchResultHighlight Component
 *
 * Component for highlighting search terms in search results.
 */

import React from 'react'
import { Typography, Box } from '@mui/material'
import { highlightText, extractSearchTerms } from '@/utils/highlightText'

export interface SearchResultHighlightProps {
  /**
   * Text to highlight
   */
  text: string
  /**
   * Search query
   */
  query: string
  /**
   * Maximum length of text to show
   */
  maxLength?: number
  /**
   * Truncate text if too long
   */
  truncate?: boolean
  /**
   * Case sensitive matching
   */
  caseSensitive?: boolean
  /**
   * Variant of typography
   */
  variant?: 'body1' | 'body2' | 'caption' | 'subtitle1' | 'subtitle2'
  /**
   * Number of lines to show (for ellipsis)
   */
  lines?: number
}

/**
 * SearchResultHighlight component
 */
export const SearchResultHighlight: React.FC<SearchResultHighlightProps> = ({
  text,
  query,
  maxLength = 200,
  truncate = true,
  caseSensitive = false,
  variant = 'body2',
  lines,
}) => {
  if (!text) return null

  const searchTerms = extractSearchTerms(query)
  let displayText = text

  // Truncate if needed
  if (truncate && text.length > maxLength) {
    // Try to truncate at word boundary
    const truncated = text.substring(0, maxLength)
    const lastSpace = truncated.lastIndexOf(' ')
    displayText = lastSpace > 0 ? truncated.substring(0, lastSpace) + '...' : truncated + '...'
  }

  const highlightedText = highlightText(displayText, searchTerms, {
    caseSensitive,
    highlightTag: 'mark',
    highlightStyle: {
      backgroundColor: 'yellow',
      padding: '2px 0',
      fontWeight: 600,
    },
  })

  const content = (
    <Typography
      variant={variant}
      sx={{
        ...(lines && {
          display: '-webkit-box',
          WebkitLineClamp: lines,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }),
      }}
    >
      {highlightedText}
    </Typography>
  )

  return <Box>{content}</Box>
}

