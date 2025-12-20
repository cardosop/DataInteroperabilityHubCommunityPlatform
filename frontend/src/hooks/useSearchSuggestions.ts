/**
 * useSearchSuggestions Hook
 *
 * Hook for managing search suggestions, recent searches, and autocomplete.
 */

import { useState, useEffect, useCallback, useRef } from 'react'

export interface SearchSuggestion {
  id: string
  text: string
  type: 'recent' | 'autocomplete' | 'trending'
  metadata?: Record<string, unknown>
}

export interface UseSearchSuggestionsOptions {
  /**
   * Storage key for recent searches
   */
  storageKey?: string
  /**
   * Maximum number of recent searches to store
   */
  maxRecentSearches?: number
  /**
   * Autocomplete function
   */
  autocompleteFn?: (query: string) => Promise<string[]> | string[]
  /**
   * Trending searches
   */
  trendingSearches?: string[]
  /**
   * Debounce delay for autocomplete
   */
  debounceMs?: number
}

/**
 * Hook for managing search suggestions
 */
export function useSearchSuggestions(options: UseSearchSuggestionsOptions = {}) {
  const {
    storageKey = 'search-recent-searches',
    maxRecentSearches = 10,
    autocompleteFn,
    trendingSearches = [],
    debounceMs = 300,
  } = options

  const [recentSearches, setRecentSearches] = useState<string[]>([])
  const [autocompleteSuggestions, setAutocompleteSuggestions] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const debounceTimeoutRef = useRef<NodeJS.Timeout>()

  // Load recent searches from localStorage
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = localStorage.getItem(storageKey)
        if (stored) {
          const parsed = JSON.parse(stored) as string[]
          setRecentSearches(parsed.slice(0, maxRecentSearches))
        }
      } catch (error) {
        console.error('Failed to load recent searches:', error)
      }
    }
  }, [storageKey, maxRecentSearches])

  // Save recent searches to localStorage
  const saveRecentSearches = useCallback(
    (searches: string[]) => {
      if (typeof window !== 'undefined') {
        try {
          localStorage.setItem(storageKey, JSON.stringify(searches.slice(0, maxRecentSearches)))
        } catch (error) {
          console.error('Failed to save recent searches:', error)
        }
      }
    },
    [storageKey, maxRecentSearches]
  )

  // Add search to recent searches
  const addRecentSearch = useCallback(
    (query: string) => {
      if (!query.trim()) return

      setRecentSearches((prev) => {
        const filtered = prev.filter((q) => q.toLowerCase() !== query.toLowerCase())
        const updated = [query, ...filtered].slice(0, maxRecentSearches)
        saveRecentSearches(updated)
        return updated
      })
    },
    [maxRecentSearches, saveRecentSearches]
  )

  // Clear recent searches
  const clearRecentSearches = useCallback(() => {
    setRecentSearches([])
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem(storageKey)
      } catch (error) {
        console.error('Failed to clear recent searches:', error)
      }
    }
  }, [storageKey])

  // Get autocomplete suggestions
  const getAutocompleteSuggestions = useCallback(
    async (query: string) => {
      if (!query.trim() || !autocompleteFn) {
        setAutocompleteSuggestions([])
        return
      }

      setIsLoading(true)
      try {
        const suggestions = await autocompleteFn(query)
        setAutocompleteSuggestions(suggestions)
      } catch (error) {
        console.error('Failed to get autocomplete suggestions:', error)
        setAutocompleteSuggestions([])
      } finally {
        setIsLoading(false)
      }
    },
    [autocompleteFn]
  )

  // Debounced autocomplete
  const debouncedAutocomplete = useCallback(
    (query: string) => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current)
      }

      debounceTimeoutRef.current = setTimeout(() => {
        getAutocompleteSuggestions(query)
      }, debounceMs)
    },
    [getAutocompleteSuggestions, debounceMs]
  )

  // Get all suggestions
  const getSuggestions = useCallback(
    (query: string): SearchSuggestion[] => {
      const suggestions: SearchSuggestion[] = []

      // Recent searches
      const matchingRecent = recentSearches
        .filter((search) => search.toLowerCase().includes(query.toLowerCase()))
        .map(
          (search, index) =>
            ({
              id: `recent-${index}`,
              text: search,
              type: 'recent' as const,
            }) as SearchSuggestion
        )
      suggestions.push(...matchingRecent)

      // Autocomplete suggestions
      const matchingAutocomplete = autocompleteSuggestions
        .filter((suggestion) => suggestion.toLowerCase().includes(query.toLowerCase()))
        .map(
          (suggestion, index) =>
            ({
              id: `autocomplete-${index}`,
              text: suggestion,
              type: 'autocomplete' as const,
            }) as SearchSuggestion
        )
      suggestions.push(...matchingAutocomplete)

      // Trending searches
      const matchingTrending = trendingSearches
        .filter((trend) => trend.toLowerCase().includes(query.toLowerCase()))
        .map(
          (trend, index) =>
            ({
              id: `trending-${index}`,
              text: trend,
              type: 'trending' as const,
            }) as SearchSuggestion
        )
      suggestions.push(...matchingTrending)

      return suggestions
    },
    [recentSearches, autocompleteSuggestions, trendingSearches]
  )

  return {
    recentSearches,
    autocompleteSuggestions,
    isLoading,
    addRecentSearch,
    clearRecentSearches,
    getAutocompleteSuggestions: debouncedAutocomplete,
    getSuggestions,
  }
}

