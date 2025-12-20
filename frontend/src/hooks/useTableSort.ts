import { useState, useMemo, useCallback } from 'react'

export type SortDirection = 'asc' | 'desc' | null

export interface SortState {
  columnId: string | null
  direction: SortDirection
}

export interface UseTableSortOptions<T> {
  /**
   * Initial sort column ID
   */
  initialSortColumn?: string | null
  /**
   * Initial sort direction
   */
  initialSortDirection?: SortDirection
  /**
   * Custom sort function for a column
   */
  getSortValue?: (row: T, columnId: string) => any
  /**
   * Whether sorting is enabled
   * @default true
   */
  enabled?: boolean
}

export interface UseTableSortReturn<T> {
  /**
   * Current sort state
   */
  sortState: SortState
  /**
   * Sorted data
   */
  sortedData: T[]
  /**
   * Handle column sort
   */
  handleSort: (columnId: string) => void
  /**
   * Set sort state programmatically
   */
  setSort: (columnId: string | null, direction: SortDirection) => void
  /**
   * Clear sort
   */
  clearSort: () => void
}

/**
 * Hook for table sorting functionality
 *
 * @example
 * ```tsx
 * const { sortedData, handleSort, sortState } = useTableSort(data, {
 *   initialSortColumn: 'name',
 *   initialSortDirection: 'asc',
 * })
 * ```
 */
export function useTableSort<T extends Record<string, any>>(
  data: T[],
  options: UseTableSortOptions<T> = {}
): UseTableSortReturn<T> {
  const {
    initialSortColumn = null,
    initialSortDirection = null,
    getSortValue,
    enabled = true,
  } = options

  const [sortState, setSortState] = useState<SortState>({
    columnId: initialSortColumn,
    direction: initialSortDirection,
  })

  const handleSort = useCallback(
    (columnId: string) => {
      if (!enabled) return

      setSortState((prev) => {
        if (prev.columnId === columnId) {
          // Cycle through: asc -> desc -> null
          if (prev.direction === 'asc') {
            return { columnId, direction: 'desc' }
          } else if (prev.direction === 'desc') {
            return { columnId: null, direction: null }
          } else {
            return { columnId, direction: 'asc' }
          }
        } else {
          return { columnId, direction: 'asc' }
        }
      })
    },
    [enabled]
  )

  const setSort = useCallback(
    (columnId: string | null, direction: SortDirection) => {
      if (!enabled) return
      setSortState({ columnId, direction })
    },
    [enabled]
  )

  const clearSort = useCallback(() => {
    setSortState({ columnId: null, direction: null })
  }, [])

  const sortedData = useMemo(() => {
    if (!sortState.columnId || !sortState.direction) {
      return [...data]
    }

    return [...data].sort((a, b) => {
      const aVal = getSortValue
        ? getSortValue(a, sortState.columnId!)
        : a[sortState.columnId!]
      const bVal = getSortValue
        ? getSortValue(b, sortState.columnId!)
        : b[sortState.columnId!]

      // Handle null/undefined values
      if (aVal == null && bVal == null) return 0
      if (aVal == null) return 1
      if (bVal == null) return -1

      // Handle different types
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        const comparison = aVal.localeCompare(bVal, undefined, {
          numeric: true,
          sensitivity: 'base',
        })
        return sortState.direction === 'asc' ? comparison : -comparison
      }

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortState.direction === 'asc' ? aVal - bVal : bVal - aVal
      }

      if (aVal instanceof Date && bVal instanceof Date) {
        return sortState.direction === 'asc'
          ? aVal.getTime() - bVal.getTime()
          : bVal.getTime() - aVal.getTime()
      }

      // Fallback to string comparison
      const aStr = String(aVal)
      const bStr = String(bVal)
      const comparison = aStr.localeCompare(bStr, undefined, {
        numeric: true,
        sensitivity: 'base',
      })
      return sortState.direction === 'asc' ? comparison : -comparison
    })
  }, [data, sortState, getSortValue])

  return {
    sortState,
    sortedData,
    handleSort,
    setSort,
    clearSort,
  }
}

