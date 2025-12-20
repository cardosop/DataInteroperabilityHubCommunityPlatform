import React, { useState } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius } from '@/styles/tokens'
import { TableSortIcon } from './TableSortIcon'

export interface TableColumn<T = any> {
  id: string
  label: string
  accessor?: (row: T) => React.ReactNode
  sortable?: boolean
  width?: string
}

export interface TableProps<T = any> {
  /**
   * Column definitions
   */
  columns: TableColumn<T>[]
  /**
   * Table data
   */
  data: T[]
  /**
   * Whether columns are sortable
   * @default false
   */
  sortable?: boolean
  /**
   * Whether table is filterable
   * @default false
   */
  filterable?: boolean
  /**
   * Whether to show pagination
   * @default false
   */
  pagination?: boolean
  /**
   * Selected row IDs
   */
  selectedRows?: string[]
  /**
   * Callback when selection changes
   */
  onSelectionChange?: (selectedIds: string[]) => void
  /**
   * Row ID accessor
   */
  getRowId?: (row: T) => string
  className?: string
}

type SortDirection = 'asc' | 'desc' | null

/**
 * Table component for data tables
 */
export function Table<T extends Record<string, any>>({
  columns,
  data,
  sortable = false,
  selectedRows = [],
  onSelectionChange,
  getRowId = (row) => row.id || String(row),
  className,
}: TableProps<T>) {
  const [sortColumn, setSortColumn] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>(null)

  const handleSort = (columnId: string) => {
    if (!sortable) return

    if (sortColumn === columnId) {
      if (sortDirection === 'asc') {
        setSortDirection('desc')
      } else if (sortDirection === 'desc') {
        setSortColumn(null)
        setSortDirection(null)
      } else {
        setSortDirection('asc')
      }
    } else {
      setSortColumn(columnId)
      setSortDirection('asc')
    }
  }

  const sortedData = [...data].sort((a, b) => {
    if (!sortColumn || !sortDirection) return 0
    const column = columns.find((col) => col.id === sortColumn)
    if (!column) return 0

    const aVal = column.accessor ? column.accessor(a) : a[sortColumn]
    const bVal = column.accessor ? column.accessor(b) : b[sortColumn]

    if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
    return 0
  })

  const handleRowSelect = (rowId: string) => {
    if (!onSelectionChange) return
    const newSelection = selectedRows.includes(rowId)
      ? selectedRows.filter((id) => id !== rowId)
      : [...selectedRows, rowId]
    onSelectionChange(newSelection)
  }

  return (
    <div className={cn('table-container', className)}>
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
                    data.length > 0 && selectedRows.length === data.length
                  }
                  onChange={(e) => {
                    if (e.target.checked) {
                      onSelectionChange(data.map(getRowId))
                    } else {
                      onSelectionChange([])
                    }
                  }}
                />
              </th>
            )}
            {columns.map((column) => (
              <th
                key={column.id}
                style={{
                  padding: spacing[3],
                  textAlign: 'left',
                  fontWeight: 500,
                  cursor: sortable && column.sortable !== false ? 'pointer' : 'default',
                  width: column.width,
                }}
                onClick={() => column.sortable !== false && handleSort(column.id)}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: spacing[1],
                  }}
                >
                  {column.label}
                  {sortable && column.sortable !== false && (
                    <TableSortIcon
                      direction={sortColumn === column.id ? sortDirection : null}
                      isActive={sortColumn === column.id}
                    />
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedData.map((row) => {
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
                    e.currentTarget.style.background = colors.semantic.actionHover
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
          })}
        </tbody>
      </table>
    </div>
  )
}

Table.displayName = 'Table'

