/**
 * MarketplaceSearch Component
 *
 * Specialized search component for marketplace with:
 * - Search input with debouncing
 * - Quick filter chips (domain, tags, pricing model)
 * - Search suggestions/autocomplete
 * - Recent searches
 * - Advanced search toggle
 */

import React, { useState, useCallback, useEffect, useRef } from 'react'
import {
  Box,
  Paper,
  TextField,
  InputAdornment,
  IconButton,
  Chip,
  Autocomplete,
  Button,
  Collapse,
  Typography,
  Divider,
} from '@mui/material'
import {
  Search as SearchIcon,
  Clear as ClearIcon,
  FilterList as FilterListIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material'
import { debounce } from '@/utils/debounce'
import type { PricingModel } from '@/lib/api/marketplace'

export interface MarketplaceSearchProps {
  /**
   * Current search query
   */
  searchQuery: string
  /**
   * Callback when search query changes
   */
  onSearchChange: (query: string) => void
  /**
   * Selected domain filter
   */
  domain?: string
  /**
   * Callback when domain filter changes
   */
  onDomainChange?: (domain: string | null) => void
  /**
   * Available domains for filtering
   */
  availableDomains?: string[]
  /**
   * Selected tags
   */
  selectedTags?: string[]
  /**
   * Callback when tags change
   */
  onTagsChange?: (tags: string[]) => void
  /**
   * Available tags for filtering
   */
  availableTags?: string[]
  /**
   * Selected pricing model filter
   */
  pricingModel?: PricingModel | ''
  /**
   * Callback when pricing model filter changes
   */
  onPricingModelChange?: (model: PricingModel | '') => void
  /**
   * Search suggestions for autocomplete
   */
  suggestions?: string[]
  /**
   * Recent searches
   */
  recentSearches?: string[]
  /**
   * Callback when recent search is clicked
   */
  onRecentSearchClick?: (query: string) => void
  /**
   * Placeholder text
   * @default 'Search contracts...'
   */
  placeholder?: string
  /**
   * Debounce delay in milliseconds
   * @default 500
   */
  debounceMs?: number
  /**
   * Show advanced filters
   * @default false
   */
  showAdvancedFilters?: boolean
  /**
   * Callback when advanced filters toggle
   */
  onAdvancedFiltersToggle?: (show: boolean) => void
  /**
   * Show quick filter chips
   * @default true
   */
  showQuickFilters?: boolean
  /**
   * Custom className
   */
  className?: string
}

/**
 * MarketplaceSearch Component
 *
 * @example
 * ```tsx
 * <MarketplaceSearch
 *   searchQuery={searchQuery}
 *   onSearchChange={setSearchQuery}
 *   domain={domainFilter}
 *   onDomainChange={setDomainFilter}
 *   availableDomains={domains}
 *   selectedTags={tags}
 *   onTagsChange={setTags}
 *   availableTags={allTags}
 *   pricingModel={pricingModelFilter}
 *   onPricingModelChange={setPricingModelFilter}
 *   suggestions={suggestions}
 *   recentSearches={recentSearches}
 *   onRecentSearchClick={handleRecentSearch}
 * />
 * ```
 */
export const MarketplaceSearch: React.FC<MarketplaceSearchProps> = ({
  searchQuery,
  onSearchChange,
  domain,
  onDomainChange,
  availableDomains = [],
  selectedTags = [],
  onTagsChange,
  availableTags = [],
  pricingModel = '',
  onPricingModelChange,
  suggestions = [],
  recentSearches = [],
  onRecentSearchClick,
  placeholder = 'Search contracts by title, description, or tags...',
  debounceMs = 500,
  showAdvancedFilters = false,
  onAdvancedFiltersToggle,
  showQuickFilters = true,
  className,
}) => {
  const [localSearchQuery, setLocalSearchQuery] = useState(searchQuery)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [showRecentSearches, setShowRecentSearches] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Debounced search handler
  const debouncedSearchRef = useRef(
    debounce((value: string) => {
      onSearchChange(value)
    }, debounceMs)
  )

  // Update local search query when prop changes
  useEffect(() => {
    setLocalSearchQuery(searchQuery)
  }, [searchQuery])

  // Handle search input change
  const handleSearchChange = useCallback(
    (value: string) => {
      setLocalSearchQuery(value)
      debouncedSearchRef.current(value)
      if (value.trim()) {
        setShowSuggestions(true)
        setShowRecentSearches(false)
      } else {
        setShowSuggestions(false)
        setShowRecentSearches(true)
      }
    },
    []
  )

  // Handle search input focus
  const handleSearchFocus = useCallback(() => {
    if (localSearchQuery.trim()) {
      setShowSuggestions(true)
    } else if (recentSearches.length > 0) {
      setShowRecentSearches(true)
    }
  }, [localSearchQuery, recentSearches.length])

  // Handle search input blur
  const handleSearchBlur = useCallback(() => {
    // Delay to allow suggestion clicks
    setTimeout(() => {
      setShowSuggestions(false)
      setShowRecentSearches(false)
    }, 200)
  }, [])

  // Handle suggestion click
  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      handleSearchChange(suggestion)
      setShowSuggestions(false)
      searchInputRef.current?.blur()
    },
    [handleSearchChange]
  )

  // Handle recent search click
  const handleRecentSearchClick = useCallback(
    (query: string) => {
      handleSearchChange(query)
      setShowRecentSearches(false)
      onRecentSearchClick?.(query)
      searchInputRef.current?.blur()
    },
    [handleSearchChange, onRecentSearchClick]
  )

  // Handle clear search
  const handleClear = useCallback(() => {
    handleSearchChange('')
    searchInputRef.current?.focus()
  }, [handleSearchChange])

  // Filter suggestions based on current query
  const filteredSuggestions = suggestions.filter((s) =>
    s.toLowerCase().includes(localSearchQuery.toLowerCase())
  )

  return (
    <Box className={className} sx={{ position: 'relative', width: '100%' }}>
      {/* Search Input */}
      <Paper
        elevation={1}
        sx={{
          p: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          borderRadius: 2,
        }}
      >
        <TextField
          inputRef={searchInputRef}
          fullWidth
          placeholder={placeholder}
          value={localSearchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          onFocus={handleSearchFocus}
          onBlur={handleSearchBlur}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon color="action" />
              </InputAdornment>
            ),
            endAdornment: localSearchQuery && (
              <InputAdornment position="end">
                <IconButton size="small" onClick={handleClear} edge="end">
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
          size="small"
        />
        {onAdvancedFiltersToggle && (
          <IconButton
            onClick={() => onAdvancedFiltersToggle(!showAdvancedFilters)}
            color={showAdvancedFilters ? 'primary' : 'default'}
          >
            {showAdvancedFilters ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            <FilterListIcon />
          </IconButton>
        )}
      </Paper>

      {/* Suggestions Dropdown */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <Paper
          elevation={4}
          sx={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            mt: 1,
            maxHeight: 300,
            overflowY: 'auto',
            zIndex: 1000,
          }}
        >
          {filteredSuggestions.map((suggestion, index) => (
            <Box
              key={index}
              onClick={() => handleSuggestionClick(suggestion)}
              sx={{
                p: 1.5,
                cursor: 'pointer',
                '&:hover': {
                  bgcolor: 'action.hover',
                },
              }}
            >
              <Typography variant="body2">{suggestion}</Typography>
            </Box>
          ))}
        </Paper>
      )}

      {/* Recent Searches Dropdown */}
      {showRecentSearches && recentSearches.length > 0 && (
        <Paper
          elevation={4}
          sx={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            mt: 1,
            maxHeight: 300,
            overflowY: 'auto',
            zIndex: 1000,
          }}
        >
          <Box sx={{ p: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ px: 1.5, py: 1 }}>
              Recent Searches
            </Typography>
            <Divider />
            {recentSearches.map((query, index) => (
              <Box
                key={index}
                onClick={() => handleRecentSearchClick(query)}
                sx={{
                  p: 1.5,
                  cursor: 'pointer',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <Typography variant="body2">{query}</Typography>
              </Box>
            ))}
          </Box>
        </Paper>
      )}

      {/* Quick Filters */}
      {showQuickFilters && (
        <Collapse in={showAdvancedFilters}>
          <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
            {/* Domain Filter */}
            {availableDomains.length > 0 && onDomainChange && (
              <Autocomplete
                size="small"
                options={availableDomains}
                value={domain || null}
                onChange={(_, newValue) => onDomainChange(newValue || null)}
                renderInput={(params) => (
                  <TextField {...params} label="Domain" placeholder="All domains" />
                )}
                sx={{ minWidth: 150 }}
              />
            )}

            {/* Tags Filter */}
            {availableTags.length > 0 && onTagsChange && (
              <Autocomplete
                multiple
                size="small"
                options={availableTags}
                value={selectedTags}
                onChange={(_, newValue) => onTagsChange(newValue)}
                renderInput={(params) => (
                  <TextField {...params} label="Tags" placeholder="Select tags" />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip
                      {...getTagProps({ index })}
                      key={option}
                      label={option}
                      size="small"
                    />
                  ))
                }
                sx={{ minWidth: 200 }}
              />
            )}

            {/* Pricing Model Filter */}
            {onPricingModelChange && (
              <Autocomplete
                size="small"
                options={['FREE', 'FREE_AUTO_APPROVE', 'REQUEST_APPROVAL'] as PricingModel[]}
                value={pricingModel || null}
                onChange={(_, newValue) => onPricingModelChange(newValue || '')}
                getOptionLabel={(option) => {
                  switch (option) {
                    case 'FREE':
                      return 'Free'
                    case 'FREE_AUTO_APPROVE':
                      return 'Free (Auto-approve)'
                    case 'REQUEST_APPROVAL':
                      return 'Request Access'
                    default:
                      return option
                  }
                }}
                renderInput={(params) => (
                  <TextField {...params} label="Access Mode" placeholder="All modes" />
                )}
                sx={{ minWidth: 180 }}
              />
            )}

            {/* Clear Filters Button */}
            {(domain || selectedTags.length > 0 || pricingModel) && (
              <Button
                size="small"
                startIcon={<ClearIcon />}
                onClick={() => {
                  onDomainChange?.(null)
                  onTagsChange?.([])
                  onPricingModelChange?.('')
                }}
                variant="outlined"
              >
                Clear Filters
              </Button>
            )}
          </Box>
        </Collapse>
      )}
    </Box>
  )
}

MarketplaceSearch.displayName = 'MarketplaceSearch'

