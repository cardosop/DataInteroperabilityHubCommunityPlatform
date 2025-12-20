import React from 'react'
import { Table, TableProps } from '../Table'

/**
 * DataGrid component - advanced table with filtering, sorting, grouping
 * For now, this is a wrapper around Table. Full implementation would include:
 * - Advanced filtering UI
 * - Column grouping
 * - Column resizing
 * - Column reordering
 * - Export functionality
 */
export function DataGrid<T extends Record<string, any>>(
  props: TableProps<T>
) {
  return <Table {...props} sortable filterable pagination />
}

DataGrid.displayName = 'DataGrid'

