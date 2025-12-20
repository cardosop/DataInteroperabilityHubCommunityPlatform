/**
 * FacetedSearch Component
 *
 * Faceted search with filter sidebar and active filters display.
 */

import React, { useState, useCallback } from 'react'
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Checkbox,
  FormControlLabel,
  Typography,
  Chip,
  IconButton,
  Divider,
  Collapse,
  Button,
} from '@mui/material'
import {
  FilterList as FilterListIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Clear as ClearIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'

export interface FacetOption {
  value: string
  label: string
  count?: number
}

export interface Facet {
  id: string
  label: string
  field: string
  options: FacetOption[]
  type: 'single' | 'multiple'
  expanded?: boolean
}

export interface FacetedSearchProps {
  /**
   * Available facets
   */
  facets: Facet[]
  /**
   * Selected facet values (field -> values[])
   */
  selectedFacets: Record<string, string[]>
  /**
   * Callback when facet selection changes
   */
  onFacetChange: (field: string, values: string[]) => void
  /**
   * Callback when all facets are cleared
   */
  onClearAll?: () => void
  /**
   * Drawer open state
   */
  drawerOpen?: boolean
  /**
   * Callback when drawer state changes
   */
  onDrawerToggle?: (open: boolean) => void
  /**
   * Show active filters
   */
  showActiveFilters?: boolean
  /**
   * Anchor position for drawer
   */
  anchor?: 'left' | 'right'
  /**
   * Width of the drawer
   */
  drawerWidth?: number
}

/**
 * FacetedSearch component
 */
export const FacetedSearch: React.FC<FacetedSearchProps> = ({
  facets,
  selectedFacets,
  onFacetChange,
  onClearAll,
  drawerOpen = false,
  onDrawerToggle,
  showActiveFilters = true,
  anchor = 'left',
  drawerWidth = 300,
}) => {
  const [expandedFacets, setExpandedFacets] = useState<Set<string>>(
    new Set(facets.filter((f) => f.expanded).map((f) => f.id))
  )

  const toggleFacet = useCallback((facetId: string) => {
    setExpandedFacets((prev) => {
      const next = new Set(prev)
      if (next.has(facetId)) {
        next.delete(facetId)
      } else {
        next.add(facetId)
      }
      return next
    })
  }, [])

  const handleFacetOptionToggle = useCallback(
    (field: string, value: string, type: 'single' | 'multiple') => {
      const currentValues = selectedFacets[field] || []
      let newValues: string[]

      if (type === 'single') {
        // Single selection - replace current value
        newValues = currentValues.includes(value) ? [] : [value]
      } else {
        // Multiple selection - toggle value
        if (currentValues.includes(value)) {
          newValues = currentValues.filter((v) => v !== value)
        } else {
          newValues = [...currentValues, value]
        }
      }

      onFacetChange(field, newValues)
    },
    [selectedFacets, onFacetChange]
  )

  const handleClearFacet = useCallback(
    (field: string) => {
      onFacetChange(field, [])
    },
    [onFacetChange]
  )

  const getActiveFiltersCount = () => {
    return Object.values(selectedFacets).reduce((sum, values) => sum + values.length, 0)
  }

  const renderFacet = (facet: Facet) => {
    const isExpanded = expandedFacets.has(facet.id)
    const selectedValues = selectedFacets[facet.field] || []
    const hasSelection = selectedValues.length > 0

    return (
      <Box key={facet.id}>
        <ListItem
          disablePadding
          secondaryAction={
            hasSelection && (
              <IconButton
                edge="end"
                size="small"
                onClick={(e) => {
                  e.stopPropagation()
                  handleClearFacet(facet.field)
                }}
              >
                <ClearIcon fontSize="small" />
              </IconButton>
            )
          }
        >
          <ListItemButton onClick={() => toggleFacet(facet.id)}>
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: spacing[1] }}>
                  <Typography variant="subtitle2">{facet.label}</Typography>
                  {hasSelection && (
                    <Chip
                      label={selectedValues.length}
                      size="small"
                      color="primary"
                      sx={{ height: 20, fontSize: '0.7rem' }}
                    />
                  )}
                </Box>
              }
            />
            {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
          </ListItemButton>
        </ListItem>
        <Collapse in={isExpanded} timeout="auto" unmountOnExit>
          <List component="div" disablePadding>
            {facet.options.map((option) => {
              const isSelected = selectedValues.includes(option.value)
              return (
                <ListItem key={option.value} disablePadding>
                  <ListItemButton
                    sx={{ pl: 4 }}
                    onClick={() =>
                      handleFacetOptionToggle(facet.field, option.value, facet.type)
                    }
                  >
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={isSelected}
                          onChange={() =>
                            handleFacetOptionToggle(facet.field, option.value, facet.type)
                          }
                          size="small"
                        />
                      }
                      label={
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                          <Typography variant="body2">{option.label}</Typography>
                          {option.count !== undefined && (
                            <Typography variant="caption" color="text.secondary">
                              ({option.count})
                            </Typography>
                          )}
                        </Box>
                      }
                      sx={{ margin: 0, width: '100%' }}
                    />
                  </ListItemButton>
                </ListItem>
              )
            })}
          </List>
        </Collapse>
        <Divider />
      </Box>
    )
  }

  const renderActiveFilters = () => {
    const activeFilters: Array<{ field: string; label: string; value: string; valueLabel: string }> = []

    facets.forEach((facet) => {
      const selectedValues = selectedFacets[facet.field] || []
      selectedValues.forEach((value) => {
        const option = facet.options.find((o) => o.value === value)
        if (option) {
          activeFilters.push({
            field: facet.field,
            label: facet.label,
            value,
            valueLabel: option.label,
          })
        }
      })
    })

    if (activeFilters.length === 0) return null

    return (
      <Box sx={{ marginBottom: spacing[2] }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing[1] }}>
          <Typography variant="subtitle2">Active Filters</Typography>
          {onClearAll && (
            <Button size="small" onClick={onClearAll}>
              Clear All
            </Button>
          )}
        </Box>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: spacing[1] }}>
          {activeFilters.map((filter, index) => (
            <Chip
              key={`${filter.field}-${filter.value}-${index}`}
              label={`${filter.label}: ${filter.valueLabel}`}
              onDelete={() => handleClearFacet(filter.field)}
              size="small"
              color="primary"
              variant="outlined"
            />
          ))}
        </Box>
      </Box>
    )
  }

  const filterSidebar = (
    <Box sx={{ padding: spacing[2] }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing[2] }}>
        <Typography variant="h6">Filters</Typography>
        {onClearAll && getActiveFiltersCount() > 0 && (
          <Button size="small" onClick={onClearAll}>
            Clear All
          </Button>
        )}
      </Box>
      <List>{facets.map(renderFacet)}</List>
    </Box>
  )

  return (
    <Box>
      {/* Active Filters Display */}
      {showActiveFilters && renderActiveFilters()}

      {/* Filter Toggle Button */}
      {onDrawerToggle && (
        <IconButton
          onClick={() => onDrawerToggle(!drawerOpen)}
          color={getActiveFiltersCount() > 0 ? 'primary' : 'default'}
          sx={{ position: 'relative' }}
        >
          <FilterListIcon />
          {getActiveFiltersCount() > 0 && (
            <Box
              sx={{
                position: 'absolute',
                top: 4,
                right: 4,
                width: 16,
                height: 16,
                borderRadius: '50%',
                backgroundColor: 'error.main',
                color: 'white',
                fontSize: '0.7rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {getActiveFiltersCount()}
            </Box>
          )}
        </IconButton>
      )}

      {/* Filter Drawer */}
      {onDrawerToggle && (
        <Drawer
          anchor={anchor}
          open={drawerOpen}
          onClose={() => onDrawerToggle(false)}
          PaperProps={{
            sx: {
              width: drawerWidth,
              maxWidth: '90vw',
            },
          }}
        >
          {filterSidebar}
        </Drawer>
      )}

      {/* Inline Filter Sidebar (when drawer is not used) */}
      {!onDrawerToggle && (
        <Box
          sx={{
            width: drawerWidth,
            borderRight: 1,
            borderColor: 'divider',
            minHeight: '100%',
          }}
        >
          {filterSidebar}
        </Box>
      )}
    </Box>
  )
}

