/**
 * Data Export Utilities
 *
 * Functions for exporting data to various formats (CSV, JSON, Excel)
 */

export interface ExportOptions {
  /**
   * Filename (without extension)
   */
  filename?: string
  /**
   * Include headers in CSV
   * @default true
   */
  includeHeaders?: boolean
  /**
   * CSV delimiter
   * @default ','
   */
  delimiter?: string
}

/**
 * Convert data to CSV format
 */
function convertToCSV<T extends Record<string, any>>(
  data: T[],
  options: ExportOptions = {}
): string {
  const { includeHeaders = true, delimiter = ',' } = options

  if (data.length === 0) return ''

  // Get all unique keys from all objects
  const keys = Array.from(
    new Set(data.flatMap((item) => Object.keys(item)))
  ) as (keyof T)[]

  const rows: string[] = []

  // Add headers
  if (includeHeaders) {
    rows.push(keys.map((key) => escapeCSVValue(String(key))).join(delimiter))
  }

  // Add data rows
  data.forEach((item) => {
    const values = keys.map((key) => {
      const value = item[key]
      return escapeCSVValue(value != null ? String(value) : '')
    })
    rows.push(values.join(delimiter))
  })

  return rows.join('\n')
}

/**
 * Escape CSV value (handles commas, quotes, newlines)
 */
function escapeCSVValue(value: string): string {
  // If value contains comma, quote, or newline, wrap in quotes and escape quotes
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replace(/"/g, '""')}"`
  }
  return value
}

/**
 * Download data as CSV file
 *
 * @example
 * ```tsx
 * exportToCSV(users, { filename: 'users-export' })
 * ```
 */
export function exportToCSV<T extends Record<string, any>>(
  data: T[],
  options: ExportOptions = {}
): void {
  const { filename = 'export' } = options
  const csv = convertToCSV(data, options)
  downloadFile(csv, `${filename}.csv`, 'text/csv;charset=utf-8;')
}

/**
 * Download data as JSON file
 *
 * @example
 * ```tsx
 * exportToJSON(users, { filename: 'users-export', pretty: true })
 * ```
 */
export function exportToJSON<T>(
  data: T,
  options: ExportOptions & { pretty?: boolean } = {}
): void {
  const { filename = 'export', pretty = false } = options
  const json = pretty
    ? JSON.stringify(data, null, 2)
    : JSON.stringify(data)
  downloadFile(json, `${filename}.json`, 'application/json;charset=utf-8;')
}

/**
 * Download data as Excel file (XLSX format using CSV with .xlsx extension)
 *
 * Note: This creates a simple Excel-compatible CSV file.
 * For full Excel support with formatting, consider using a library like 'xlsx'.
 *
 * @example
 * ```tsx
 * exportToExcel(users, { filename: 'users-export' })
 * ```
 */
export function exportToExcel<T extends Record<string, any>>(
  data: T[],
  options: ExportOptions = {}
): void {
  const { filename = 'export' } = options
  const csv = convertToCSV(data, { ...options, delimiter: ',' })

  // Excel can open CSV files, but we'll use .xlsx extension
  // For full Excel support, you'd need to use a library like 'xlsx'
  downloadFile(csv, `${filename}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
}

/**
 * Download file to user's computer
 */
function downloadFile(
  content: string,
  filename: string,
  mimeType: string
): void {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Export data with custom formatter
 *
 * @example
 * ```tsx
 * exportData(users, {
 *   format: 'csv',
 *   filename: 'users',
 *   formatter: (user) => ({
 *     name: user.fullName,
 *     email: user.emailAddress,
 *   }),
 * })
 * ```
 */
export function exportData<T extends Record<string, any>>(
  data: T[],
  options: ExportOptions & {
    format: 'csv' | 'json' | 'excel'
    formatter?: (item: T) => Record<string, any>
  }
): void {
  const { format, formatter, ...exportOptions } = options

  let processedData = data
  if (formatter) {
    processedData = data.map(formatter) as T[]
  }

  switch (format) {
    case 'csv':
      exportToCSV(processedData, exportOptions)
      break
    case 'json':
      exportToJSON(processedData, exportOptions)
      break
    case 'excel':
      exportToExcel(processedData, exportOptions)
      break
    default:
      throw new Error(`Unsupported export format: ${format}`)
  }
}

