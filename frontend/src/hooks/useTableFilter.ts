import { useState, useMemo, useCallback } from 'react'

export interface ColumnFilter<T = any> {
  columnId: string
  value: string
  filterFn?: (row: T, value: string) => boolean
}

export interface UseTableFilterOptions<T> {
  /**
   * Global search value
   */
  globalSearch?: string
  /**
   * Columns to search in global search
   */
  globalSearchColumns?: string[]
  /**
   * Custom global search function
   */
  globalSearchFn?: (row: T, searchValue: string) => boolean
  /**
   * Column-specific filters
   */
  columnFilters?: ColumnFilter<T>[]
  /**
   * Whether filtering is enabled
   * @default true
   */
  enabled?: boolean
}

export interface UseTableFilterReturn<T> {
  /**
   * Global search value
   */
  globalSearch: string
  /**
   * Set global search value
   */
  setGlobalSearch: (value: string) => void
  /**
   * Column filters
   */
  columnFilters: ColumnFilter<T>[]
  /**
   * Set column filter
   */
  setColumnFilter: (columnId: string, value: string, filterFn?: (row: T, value: string) => boolean) => void
  /**
   * Clear column filter
   */
  clearColumnFilter: (columnId: string) => void
  /**
   * Clear all filters
   */
  clearAllFilters: () => void
  /**
   * Filtered data
   */
  filteredData: T[]
  /**
   * Active filter count
   */
  activeFilterCount: number
}

/**
 * Default filter function for string matching
 */
function defaultFilterFn<T>(row: T, columnId: string, value: string): boolean {
  const cellValue = String((row as any)[columnId] || '').toLowerCase()
  return cellValue.includes(value.toLowerCase())
}

/**
 * Default global search function
 */
function defaultGlobalSearchFn<T>(
  row: T,
  searchValue: string,
  columns: string[]
): boolean {
  const searchLower = searchValue.toLowerCase()
  return columns.some((columnId) => {
    const cellValue = String((row as any)[columnId] || '').toLowerCase()
    return cellValue.includes(searchLower)
  })
}

/**
 * Hook for table filtering functionality
 *
 * @example
 * ```tsx
 * const {
 *   filteredData,
 *   globalSearch,
 *   setGlobalSearch,
 *   setColumnFilter,
 * } = useTableFilter(data, {
 *   globalSearchColumns: ['name', 'email'],
 * })
 * ```
 */
export function useTableFilter<T extends Record<string, any>>(
  data: T[],
  options: UseTableFilterOptions<T> = {}
): UseTableFilterReturn<T> {
  const {
    globalSearch: initialGlobalSearch = '',
    globalSearchColumns = [],
    globalSearchFn,
    columnFilters: initialColumnFilters = [],
    enabled = true,
  } = options

  const [globalSearch, setGlobalSearch] = useState(initialGlobalSearch)
  const [columnFilters, setColumnFilters] = useState<ColumnFilter<T>[]>(
    initialColumnFilters
  )

  const setColumnFilter = useCallback(
    (
      columnId: string,
      value: string,
      filterFn?: (row: T, value: string) => boolean
    ) => {
      if (!enabled) return

      setColumnFilters((prev) => {
        const existing = prev.findIndex((f) => f.columnId === columnId)
        if (value === '') {
          // Remove filter if value is empty
          return prev.filter((f) => f.columnId !== columnId)
        }
        const newFilter: ColumnFilter<T> = {
          columnId,
          value,
          filterFn,
        }
        if (existing >= 0) {
          const updated = [...prev]
          updated[existing] = newFilter
          return updated
        }
        return [...prev, newFilter]
      })
    },
    [enabled]
  )

  const clearColumnFilter = useCallback(
    (columnId: string) => {
      setColumnFilters((prev) => prev.filter((f) => f.columnId !== columnId))
    },
    []
  )

  const clearAllFilters = useCallback(() => {
    setGlobalSearch('')
    setColumnFilters([])
  }, [])

  const filteredData = useMemo(() => {
    if (!enabled) return data

    let result = [...data]

    // Apply global search
    if (globalSearch.trim()) {
      if (globalSearchFn) {
        result = result.filter((row) => globalSearchFn(row, globalSearch))
      } else if (globalSearchColumns.length > 0) {
        result = result.filter((row) =>
          defaultGlobalSearchFn(row, globalSearch, globalSearchColumns)
        )
      }
    }

    // Apply column filters
    columnFilters.forEach((filter) => {
      if (filter.value.trim()) {
        const filterFunction =
          filter.filterFn ||
          ((row: T) => defaultFilterFn(row, filter.columnId, filter.value))
        result = result.filter((row) => filterFunction(row, filter.value))
      }
    })

    return result
  }, [
    data,
    globalSearch,
    globalSearchColumns,
    globalSearchFn,
    columnFilters,
    enabled,
  ])

  const activeFilterCount = useMemo(() => {
    let count = 0
    if (globalSearch.trim()) count++
    count += columnFilters.filter((f) => f.value.trim()).length
    return count
  }, [globalSearch, columnFilters])

  return {
    globalSearch,
    setGlobalSearch,
    columnFilters,
    setColumnFilter,
    clearColumnFilter,
    clearAllFilters,
    filteredData,
    activeFilterCount,
  }
}

