/**
 * useSearchFiltersPersistence Hook
 *
 * Hook for persisting search filters and preferences to localStorage.
 */

import { useState, useEffect, useCallback } from 'react'

export interface SearchFilters {
  query?: string
  filters?: Record<string, unknown>
  facets?: Record<string, string[]>
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  pageSize?: number
}

export interface UseSearchFiltersPersistenceOptions {
  /**
   * Storage key for filters
   */
  storageKey?: string
  /**
   * Auto-save filters on change
   */
  autoSave?: boolean
  /**
   * Debounce delay for auto-save
   */
  debounceMs?: number
}

/**
 * Hook for persisting search filters
 */
export function useSearchFiltersPersistence(
  options: UseSearchFiltersPersistenceOptions = {}
) {
  const {
    storageKey = 'search-filters',
    autoSave = true,
    debounceMs = 500,
  } = options

  const [filters, setFilters] = useState<SearchFilters>({})
  const [isLoading, setIsLoading] = useState(true)
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Load filters from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem(storageKey)
        if (stored) {
          const parsed = JSON.parse(stored) as SearchFilters
          setFilters(parsed)
        }
      } catch (error) {
        console.error('Failed to load search filters:', error)
      } finally {
        setIsLoading(false)
      }
    } else {
      setIsLoading(false)
    }
  }, [storageKey])

  // Save filters to localStorage
  const saveFilters = useCallback(
    (newFilters: SearchFilters) => {
      if (typeof window !== 'undefined') {
        try {
          localStorage.setItem(storageKey, JSON.stringify(newFilters))
        } catch (error) {
          console.error('Failed to save search filters:', error)
        }
      }
    },
    [storageKey]
  )

  // Update filters
  const updateFilters = useCallback(
    (updates: Partial<SearchFilters>) => {
      setFilters((prev) => {
        const updated = { ...prev, ...updates }

        if (autoSave) {
          // Clear existing timeout
          if (debounceTimeoutRef.current) {
            clearTimeout(debounceTimeoutRef.current)
          }

          // Debounce save
          debounceTimeoutRef.current = setTimeout(() => {
            saveFilters(updated)
          }, debounceMs)
        }

        return updated
      })
    },
    [autoSave, debounceMs, saveFilters]
  )

  // Clear filters
  const clearFilters = useCallback(() => {
    setFilters({})
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem(storageKey)
      } catch (error) {
        console.error('Failed to clear search filters:', error)
      }
    }
  }, [storageKey])

  // Reset to default filters
  const resetFilters = useCallback(
    (defaultFilters: SearchFilters = {}) => {
      setFilters(defaultFilters)
      if (autoSave) {
        saveFilters(defaultFilters)
      }
    },
    [autoSave, saveFilters]
  )

  // Save filters immediately (bypass debounce)
  const saveFiltersNow = useCallback(() => {
    saveFilters(filters)
  }, [filters, saveFilters])

  return {
    filters,
    isLoading,
    updateFilters,
    clearFilters,
    resetFilters,
    saveFiltersNow,
  }
}

