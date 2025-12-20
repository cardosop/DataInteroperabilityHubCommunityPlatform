/**
 * SearchSuggestions Component
 *
 * Search suggestions with autocomplete and recent searches.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Box,
  Paper,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Typography,
  Divider,
  IconButton,
  Chip,
} from '@mui/material'
import {
  Search as SearchIcon,
  History as HistoryIcon,
  TrendingUp as TrendingIcon,
  Clear as ClearIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'

export interface SearchSuggestion {
  id: string
  text: string
  type: 'recent' | 'autocomplete' | 'trending'
  metadata?: Record<string, unknown>
}

export interface SearchSuggestionsProps {
  /**
   * Current search query
   */
  query: string
  /**
   * Suggestions to display
   */
  suggestions: SearchSuggestion[]
  /**
   * Callback when suggestion is selected
   */
  onSuggestionSelect: (suggestion: string) => void
  /**
   * Callback when recent search is cleared
   */
  onClearRecent?: () => void
  /**
   * Whether suggestions are visible
   */
  visible: boolean
  /**
   * Maximum number of suggestions to show
   */
  maxSuggestions?: number
  /**
   * Show recent searches
   */
  showRecent?: boolean
  /**
   * Show trending searches
   */
  showTrending?: boolean
  /**
   * Anchor element for positioning
   */
  anchorEl?: HTMLElement | null
}

/**
 * SearchSuggestions component
 */
export const SearchSuggestions: React.FC<SearchSuggestionsProps> = ({
  query,
  suggestions,
  onSuggestionSelect,
  onClearRecent,
  visible,
  maxSuggestions = 10,
  showRecent = true,
  showTrending = true,
  anchorEl,
}) => {
  const [position, setPosition] = useState<{ top: number; left: number; width: number } | null>(null)
  const paperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (anchorEl && visible) {
      const rect = anchorEl.getBoundingClientRect()
      setPosition({
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
      })
    } else {
      setPosition(null)
    }
  }, [anchorEl, visible])

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      onSuggestionSelect(suggestion)
    },
    [onSuggestionSelect]
  )

  const highlightText = (text: string, highlight: string) => {
    if (!highlight) return text
    const parts = text.split(new RegExp(`(${highlight})`, 'gi'))
    return (
      <>
        {parts.map((part, index) =>
          part.toLowerCase() === highlight.toLowerCase() ? (
            <mark key={index} style={{ backgroundColor: 'yellow', padding: 0 }}>
              {part}
            </mark>
          ) : (
            part
          )
        )}
      </>
    )
  }

  const groupedSuggestions = suggestions.reduce(
    (acc, suggestion) => {
      if (!acc[suggestion.type]) {
        acc[suggestion.type] = []
      }
      acc[suggestion.type].push(suggestion)
      return acc
    },
    {} as Record<string, SearchSuggestion[]>
  )

  const recentSearches = groupedSuggestions.recent || []
  const autocompleteSuggestions = groupedSuggestions.autocomplete || []
  const trendingSearches = groupedSuggestions.trending || []

  if (!visible || suggestions.length === 0) return null

  const renderSuggestion = (suggestion: SearchSuggestion, index: number) => {
    const getIcon = () => {
      switch (suggestion.type) {
        case 'recent':
          return <HistoryIcon fontSize="small" />
        case 'trending':
          return <TrendingIcon fontSize="small" />
        default:
          return <SearchIcon fontSize="small" />
      }
    }

    return (
      <ListItem key={suggestion.id || index} disablePadding>
        <ListItemButton onClick={() => handleSuggestionClick(suggestion.text)}>
          <ListItemIcon sx={{ minWidth: 36 }}>{getIcon()}</ListItemIcon>
          <ListItemText
            primary={highlightText(suggestion.text, query)}
            secondary={
              suggestion.type === 'trending' ? (
                <Chip label="Trending" size="small" sx={{ height: 18, fontSize: '0.65rem', marginTop: 0.5 }} />
              ) : null
            }
          />
        </ListItemButton>
      </ListItem>
    )
  }

  return (
    <Paper
      ref={paperRef}
      elevation={4}
      sx={{
        position: 'absolute',
        top: position?.top,
        left: position?.left,
        width: position?.width || '100%',
        maxHeight: '400px',
        overflow: 'auto',
        zIndex: 1300,
        marginTop: spacing[1],
      }}
    >
      {/* Recent Searches */}
      {showRecent && recentSearches.length > 0 && (
        <Box>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: spacing[2],
              paddingBottom: spacing[1],
            }}
          >
            <Typography variant="caption" color="text.secondary" fontWeight={500}>
              Recent Searches
            </Typography>
            {onClearRecent && (
              <IconButton size="small" onClick={onClearRecent}>
                <ClearIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
          <List dense>
            {recentSearches.slice(0, maxSuggestions).map((suggestion, index) => renderSuggestion(suggestion, index))}
          </List>
          {(autocompleteSuggestions.length > 0 || trendingSearches.length > 0) && <Divider />}
        </Box>
      )}

      {/* Autocomplete Suggestions */}
      {autocompleteSuggestions.length > 0 && (
        <Box>
          {recentSearches.length > 0 && (
            <Box sx={{ padding: spacing[1], paddingLeft: spacing[2] }}>
              <Typography variant="caption" color="text.secondary" fontWeight={500}>
                Suggestions
              </Typography>
            </Box>
          )}
          <List dense>
            {autocompleteSuggestions.slice(0, maxSuggestions).map((suggestion, index) =>
              renderSuggestion(suggestion, index)
            )}
          </List>
          {trendingSearches.length > 0 && <Divider />}
        </Box>
      )}

      {/* Trending Searches */}
      {showTrending && trendingSearches.length > 0 && (
        <Box>
          {(recentSearches.length > 0 || autocompleteSuggestions.length > 0) && (
            <Box sx={{ padding: spacing[1], paddingLeft: spacing[2] }}>
              <Typography variant="caption" color="text.secondary" fontWeight={500}>
                Trending
              </Typography>
            </Box>
          )}
          <List dense>
            {trendingSearches.slice(0, maxSuggestions).map((suggestion, index) => renderSuggestion(suggestion, index))}
          </List>
        </Box>
      )}
    </Paper>
  )
}

