import React, { useMemo } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'
import { useTableSort } from '@/hooks/useTableSort'
import { useTableFilter } from '@/hooks/useTableFilter'
import { TableSortIcon } from './TableSortIcon'
import { SearchBar } from '@/components/forms/SearchBar'
import type { TableColumn, TableProps } from './Table'

export interface EnhancedTableProps<T = any> extends Omit<TableProps<T>, 'sortable' | 'filterable'> {
  /**
   * Whether columns are sortable
   * @default true
   */
  sortable?: boolean
  /**
   * Whether table is filterable
   * @default true
   */
  filterable?: boolean
  /**
   * Columns to include in global search
   */
  globalSearchColumns?: string[]
  /**
   * Custom global search function
   */
  globalSearchFn?: (row: T, searchValue: string) => boolean
  /**
   * Show global search bar
   * @default true
   */
  showGlobalSearch?: boolean
  /**
   * Placeholder for global search
   */
  searchPlaceholder?: string
  /**
   * Show column filters
   * @default false
   */
  showColumnFilters?: boolean
}

/**
 * Enhanced Table component with sorting and filtering
 *
 * Features:
 * - Click header to sort with visual indicators
 * - Global search across specified columns
 * - Column-specific filters
 * - Combines sorting and filtering
 */
export function EnhancedTable<T extends Record<string, any>>({
  columns,
  data,
  sortable = true,
  filterable = true,
  globalSearchColumns,
  globalSearchFn,
  showGlobalSearch = true,
  searchPlaceholder = 'Search...',
  showColumnFilters = false,
  selectedRows = [],
  onSelectionChange,
  getRowId = (row) => row.id || String(row),
  className,
}: EnhancedTableProps<T>) {
  // Get sortable columns
  const sortableColumns = useMemo(() => {
    return columns.filter((col) => col.sortable !== false)
  }, [columns])

  // Table sorting
  const { sortedData: sortOnlyData, handleSort, sortState } = useTableSort(
    data,
    {
      enabled: sortable,
      getSortValue: (row, columnId) => {
        const column = columns.find((col) => col.id === columnId)
        return column?.accessor ? column.accessor(row) : row[columnId]
      },
    }
  )

  // Determine columns for global search
  const searchColumns = useMemo(() => {
    if (globalSearchColumns) return globalSearchColumns
    return columns.map((col) => col.id)
  }, [columns, globalSearchColumns])

  // Table filtering
  const {
    filteredData,
    globalSearch,
    setGlobalSearch,
    setColumnFilter,
    activeFilterCount,
  } = useTableFilter(sortOnlyData, {
    enabled: filterable,
    globalSearchColumns: searchColumns,
    globalSearchFn,
  })

  // Final data (sorted and filtered)
  const displayData = filteredData

  const handleRowSelect = (rowId: string) => {
    if (!onSelectionChange) return
    const newSelection = selectedRows.includes(rowId)
      ? selectedRows.filter((id) => id !== rowId)
      : [...selectedRows, rowId]
    onSelectionChange(newSelection)
  }

  return (
    <div className={cn('enhanced-table-container', className)}>
      {/* Global Search */}
      {filterable && showGlobalSearch && (
        <div
          style={{
            marginBottom: spacing[4],
          }}
        >
          <SearchBar
            value={globalSearch}
            onChange={setGlobalSearch}
            placeholder={searchPlaceholder}
            showClear
          />
          {activeFilterCount > 0 && (
            <div
              style={{
                marginTop: spacing[2],
                fontSize: '12px',
                color: colors.semantic.textSecondary,
              }}
            >
              {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div
        className="table-container"
        style={{
          border: `1px solid ${colors.semantic.borderDivider}`,
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '14px',
          }}
        >
          <thead>
            <tr
              style={{
                background: colors.gray[100],
                borderBottom: `1px solid ${colors.semantic.borderDivider}`,
              }}
            >
              {onSelectionChange && (
                <th
                  style={{
                    padding: spacing[3],
                    textAlign: 'left',
                    width: '40px',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={
                      displayData.length > 0 &&
                      selectedRows.length === displayData.length
                    }
                    onChange={(e) => {
                      if (e.target.checked) {
                        onSelectionChange(displayData.map(getRowId))
                      } else {
                        onSelectionChange([])
                      }
                    }}
                    aria-label="Select all"
                  />
                </th>
              )}
              {columns.map((column) => {
                const isSortable =
                  sortable && column.sortable !== false
                const isSorted = sortState.columnId === column.id
                const sortDirection = isSorted ? sortState.direction : null

                return (
                  <th
                    key={column.id}
                    style={{
                      padding: spacing[3],
                      textAlign: 'left',
                      fontWeight: 500,
                      cursor: isSortable ? 'pointer' : 'default',
                      width: column.width,
                      userSelect: 'none',
                    }}
                    onClick={() => isSortable && handleSort(column.id)}
                    onMouseEnter={(e) => {
                      if (isSortable) {
                        e.currentTarget.style.background =
                          colors.semantic.actionHover
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = colors.gray[100]
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: spacing[1],
                      }}
                    >
                      <span>{column.label}</span>
                      {isSortable && (
                        <TableSortIcon
                          direction={sortDirection}
                          isActive={isSorted}
                        />
                      )}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {displayData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (onSelectionChange ? 1 : 0)}
                  style={{
                    padding: spacing[8],
                    textAlign: 'center',
                    color: colors.semantic.textSecondary,
                  }}
                >
                  No data available
                </td>
              </tr>
            ) : (
              displayData.map((row) => {
                const rowId = getRowId(row)
                const isSelected = selectedRows.includes(rowId)
                return (
                  <tr
                    key={rowId}
                    style={{
                      borderBottom: `1px solid ${colors.semantic.borderDivider}`,
                      background: isSelected
                        ? colors.primary[50]
                        : 'transparent',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background =
                          colors.semantic.actionHover
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.background = 'transparent'
                      }
                    }}
                  >
                    {onSelectionChange && (
                      <td style={{ padding: spacing[3] }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleRowSelect(rowId)}
                          aria-label={`Select row ${rowId}`}
                        />
                      </td>
                    )}
                    {columns.map((column) => (
                      <td key={column.id} style={{ padding: spacing[3] }}>
                        {column.accessor
                          ? column.accessor(row)
                          : row[column.id] || ''}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

EnhancedTable.displayName = 'EnhancedTable'

