/**
 * AdvancedSearch Component
 *
 * Advanced search component with multiple filters, operators, and query building.
 */

import React, { useState, useCallback } from 'react'
import {
  Box,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Chip,
  Paper,
  Typography,
  IconButton,
  Collapse,
} from '@mui/material'
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Search as SearchIcon,
} from '@mui/icons-material'
import { spacing } from '@/styles/tokens'

export type SearchOperator = 'AND' | 'OR' | 'NOT'
export type FilterField = string
export type FilterValue = string | number | boolean | string[]

export interface SearchFilter {
  id: string
  field: FilterField
  operator: 'equals' | 'contains' | 'startsWith' | 'endsWith' | 'greaterThan' | 'lessThan' | 'between' | 'in'
  value: FilterValue
  logicalOperator?: SearchOperator
}

export interface AdvancedSearchProps {
  /**
   * Available filter fields
   */
  fields: Array<{ value: string; label: string; type: 'text' | 'number' | 'date' | 'select' | 'multiselect' }>
  /**
   * Current search query
   */
  query: string
  /**
   * Current filters
   */
  filters: SearchFilter[]
  /**
   * Callback when query changes
   */
  onQueryChange: (query: string) => void
  /**
   * Callback when filters change
   */
  onFiltersChange: (filters: SearchFilter[]) => void
  /**
   * Callback when search is executed
   */
  onSearch: (query: string, filters: SearchFilter[]) => void
  /**
   * Show advanced options
   */
  showAdvanced?: boolean
  /**
   * Placeholder text
   */
  placeholder?: string
}

/**
 * AdvancedSearch component
 */
export const AdvancedSearch: React.FC<AdvancedSearchProps> = ({
  fields,
  query,
  filters,
  onQueryChange,
  onFiltersChange,
  onSearch,
  showAdvanced = false,
  placeholder = 'Search...',
}) => {
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(showAdvanced)

  const addFilter = useCallback(() => {
    const newFilter: SearchFilter = {
      id: `filter-${Date.now()}-${Math.random()}`,
      field: fields[0]?.value || '',
      operator: 'equals',
      value: '',
      logicalOperator: filters.length > 0 ? 'AND' : undefined,
    }
    onFiltersChange([...filters, newFilter])
  }, [fields, filters, onFiltersChange])

  const removeFilter = useCallback(
    (id: string) => {
      onFiltersChange(filters.filter((f) => f.id !== id))
    },
    [filters, onFiltersChange]
  )

  const updateFilter = useCallback(
    (id: string, updates: Partial<SearchFilter>) => {
      onFiltersChange(
        filters.map((f) => (f.id === id ? { ...f, ...updates } : f))
      )
    },
    [filters, onFiltersChange]
  )

  const handleSearch = useCallback(() => {
    onSearch(query, filters)
  }, [query, filters, onSearch])

  const getFieldType = (fieldValue: string) => {
    return fields.find((f) => f.value === fieldValue)?.type || 'text'
  }

  const getOperatorsForType = (type: string) => {
    switch (type) {
      case 'text':
        return [
          { value: 'equals', label: 'Equals' },
          { value: 'contains', label: 'Contains' },
          { value: 'startsWith', label: 'Starts with' },
          { value: 'endsWith', label: 'Ends with' },
        ]
      case 'number':
        return [
          { value: 'equals', label: 'Equals' },
          { value: 'greaterThan', label: 'Greater than' },
          { value: 'lessThan', label: 'Less than' },
          { value: 'between', label: 'Between' },
        ]
      case 'date':
        return [
          { value: 'equals', label: 'Equals' },
          { value: 'greaterThan', label: 'After' },
          { value: 'lessThan', label: 'Before' },
          { value: 'between', label: 'Between' },
        ]
      case 'select':
      case 'multiselect':
        return [
          { value: 'equals', label: 'Equals' },
          { value: 'in', label: 'In' },
        ]
      default:
        return [{ value: 'equals', label: 'Equals' }]
    }
  }

  const renderFilterValue = (filter: SearchFilter) => {
    const fieldType = getFieldType(filter.field)
    const field = fields.find((f) => f.value === filter.field)

    if (fieldType === 'multiselect' || filter.operator === 'in') {
      return (
        <TextField
          size="small"
          placeholder="Comma-separated values"
          value={Array.isArray(filter.value) ? filter.value.join(', ') : filter.value}
          onChange={(e) => {
            const values = e.target.value.split(',').map((v) => v.trim()).filter(Boolean)
            updateFilter(filter.id, { value: values })
          }}
          sx={{ minWidth: 200 }}
        />
      )
    }

    if (fieldType === 'select') {
      // Assuming field has options - would need to extend interface
      return (
        <TextField
          size="small"
          value={filter.value}
          onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
          sx={{ minWidth: 200 }}
        />
      )
    }

    if (filter.operator === 'between') {
      const values = Array.isArray(filter.value) ? filter.value : ['', '']
      return (
        <Box sx={{ display: 'flex', gap: spacing[1], alignItems: 'center' }}>
          <TextField
            size="small"
            type={fieldType === 'number' ? 'number' : fieldType === 'date' ? 'date' : 'text'}
            placeholder="From"
            value={values[0]}
            onChange={(e) => {
              updateFilter(filter.id, { value: [e.target.value, values[1]] })
            }}
            sx={{ minWidth: 120 }}
          />
          <Typography variant="body2">to</Typography>
          <TextField
            size="small"
            type={fieldType === 'number' ? 'number' : fieldType === 'date' ? 'date' : 'text'}
            placeholder="To"
            value={values[1]}
            onChange={(e) => {
              updateFilter(filter.id, { value: [values[0], e.target.value] })
            }}
            sx={{ minWidth: 120 }}
          />
        </Box>
      )
    }

    return (
      <TextField
        size="small"
        type={fieldType === 'number' ? 'number' : fieldType === 'date' ? 'date' : 'text'}
        value={filter.value}
        onChange={(e) => updateFilter(filter.id, { value: e.target.value })}
        placeholder="Value"
        sx={{ minWidth: 200 }}
      />
    )
  }

  return (
    <Box>
      {/* Main Search Bar */}
      <Box sx={{ display: 'flex', gap: spacing[2], marginBottom: spacing[2] }}>
        <TextField
          fullWidth
          placeholder={placeholder}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleSearch()
            }
          }}
          InputProps={{
            startAdornment: <SearchIcon sx={{ marginRight: spacing[1], color: 'text.secondary' }} />,
          }}
        />
        <Button variant="contained" onClick={handleSearch} startIcon={<SearchIcon />}>
          Search
        </Button>
      </Box>

      {/* Advanced Filters Toggle */}
      <Box sx={{ marginBottom: spacing[2] }}>
        <Button
          size="small"
          onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
          endIcon={isAdvancedOpen ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        >
          {isAdvancedOpen ? 'Hide' : 'Show'} Advanced Filters
        </Button>
      </Box>

      {/* Advanced Filters */}
      <Collapse in={isAdvancedOpen}>
        <Paper sx={{ padding: spacing[3], marginBottom: spacing[2] }}>
          <Typography variant="subtitle2" gutterBottom>
            Filters
          </Typography>
          {filters.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ marginTop: spacing[2] }}>
              No filters applied. Click "Add Filter" to add one.
            </Typography>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[2], marginTop: spacing[2] }}>
              {filters.map((filter, index) => (
                <Box
                  key={filter.id}
                  sx={{
                    display: 'flex',
                    gap: spacing[2],
                    alignItems: 'flex-start',
                    flexWrap: 'wrap',
                  }}
                >
                  {index > 0 && (
                    <FormControl size="small" sx={{ minWidth: 100 }}>
                      <Select
                        value={filter.logicalOperator || 'AND'}
                        onChange={(e) =>
                          updateFilter(filter.id, {
                            logicalOperator: e.target.value as SearchOperator,
                          })
                        }
                      >
                        <MenuItem value="AND">AND</MenuItem>
                        <MenuItem value="OR">OR</MenuItem>
                        <MenuItem value="NOT">NOT</MenuItem>
                      </Select>
                    </FormControl>
                  )}
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>Field</InputLabel>
                    <Select
                      value={filter.field}
                      label="Field"
                      onChange={(e) => {
                        const newField = e.target.value
                        const fieldType = getFieldType(newField)
                        const operators = getOperatorsForType(fieldType)
                        updateFilter(filter.id, {
                          field: newField,
                          operator: operators[0]?.value as SearchFilter['operator'],
                          value: '',
                        })
                      }}
                    >
                      {fields.map((field) => (
                        <MenuItem key={field.value} value={field.value}>
                          {field.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>Operator</InputLabel>
                    <Select
                      value={filter.operator}
                      label="Operator"
                      onChange={(e) =>
                        updateFilter(filter.id, {
                          operator: e.target.value as SearchFilter['operator'],
                          value: filter.operator === 'between' ? ['', ''] : '',
                        })
                      }
                    >
                      {getOperatorsForType(getFieldType(filter.field)).map((op) => (
                        <MenuItem key={op.value} value={op.value}>
                          {op.label}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {renderFilterValue(filter)}
                  <IconButton
                    size="small"
                    onClick={() => removeFilter(filter.id)}
                    color="error"
                  >
                    <DeleteIcon />
                  </IconButton>
                </Box>
              ))}
            </Box>
          )}
          <Button
            startIcon={<AddIcon />}
            onClick={addFilter}
            variant="outlined"
            size="small"
            sx={{ marginTop: spacing[2] }}
          >
            Add Filter
          </Button>
        </Paper>
      </Collapse>

      {/* Active Filters Summary */}
      {filters.length > 0 && (
        <Box sx={{ display: 'flex', gap: spacing[1], flexWrap: 'wrap', marginTop: spacing[2] }}>
          <Typography variant="body2" sx={{ alignSelf: 'center' }}>
            Active filters:
          </Typography>
          {filters.map((filter) => {
            const field = fields.find((f) => f.value === filter.field)
            const valueDisplay = Array.isArray(filter.value)
              ? filter.value.join(', ')
              : String(filter.value)
            return (
              <Chip
                key={filter.id}
                label={`${field?.label || filter.field} ${filter.operator} ${valueDisplay}`}
                onDelete={() => removeFilter(filter.id)}
                size="small"
              />
            )
          })}
        </Box>
      )}
    </Box>
  )
}

