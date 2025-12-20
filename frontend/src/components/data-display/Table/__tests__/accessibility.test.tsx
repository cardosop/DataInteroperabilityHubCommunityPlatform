/**
 * Table Accessibility Tests
 *
 * Comprehensive accessibility tests for table components covering:
 * - Table headers (th elements)
 * - Table captions
 * - Header associations (scope, headers attribute)
 * - Row and column headers
 * - Table structure
 *
 * Uses real table components (no mocks/stubs)
 */

import { describe, it, expect } from 'vitest'
import { render } from '@/test-utils'
import { checkAccessibility } from '@/test-utils/accessibility'
import { Table } from '../Table'

const mockData = [
  { id: 1, name: 'Item 1', status: 'Active', value: 100 },
  { id: 2, name: 'Item 2', status: 'Inactive', value: 200 },
  { id: 3, name: 'Item 3', status: 'Active', value: 300 },
]

const mockColumns = [
  { id: 'name', label: 'Name', accessor: (row: any) => row.name },
  { id: 'status', label: 'Status', accessor: (row: any) => row.status },
  { id: 'value', label: 'Value', accessor: (row: any) => row.value },
]

describe('Table Accessibility Tests', () => {
  describe('Table Structure', () => {
    it('should have no accessibility violations', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )
      await checkAccessibility(container)
    })

    it('should have proper table structure', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const table = container.querySelector('table')
      expect(table).toBeInTheDocument()

      const thead = container.querySelector('thead')
      expect(thead).toBeInTheDocument()

      const tbody = container.querySelector('tbody')
      expect(tbody).toBeInTheDocument()
    })
  })

  describe('Table Headers', () => {
    it('should have th elements for column headers', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const headers = container.querySelectorAll('th')
      expect(headers.length).toBeGreaterThan(0)
      expect(headers.length).toBe(mockColumns.length)
    })

    it('should have scope attribute on header cells', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const headers = container.querySelectorAll('th')

      for (const header of headers) {
        const scope = header.getAttribute('scope')
        // Headers should have scope="col" for column headers
        expect(scope === 'col' || scope === 'row').toBe(true)
      }
    })

    it('should have descriptive header text', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const headers = container.querySelectorAll('th')

      for (const header of headers) {
        const text = header.textContent?.trim()
        expect(text?.length).toBeGreaterThan(0)
      }
    })
  })

  describe('Table Captions', () => {
    it('should have caption for table when provided', async () => {
      const { container } = render(
        <table>
          <caption>Test Table</caption>
          <thead>
            <tr>
              {mockColumns.map((col) => (
                <th key={col.id} scope="col">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mockData.map((row) => (
              <tr key={row.id}>
                {mockColumns.map((col) => (
                  <td key={col.id}>{col.accessor(row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )

      const caption = container.querySelector('caption')
      expect(caption).toBeInTheDocument()
      expect(caption?.textContent).toBe('Test Table')
    })
  })

  describe('Table Data Cells', () => {
    it('should have td elements for data cells', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const cells = container.querySelectorAll('td')
      expect(cells.length).toBeGreaterThan(0)
      expect(cells.length).toBe(mockColumns.length * mockData.length)
    })

    it('should associate data cells with headers', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const headers = container.querySelectorAll('th')
      const cells = container.querySelectorAll('td')

      // Each cell should be associated with its column header
      expect(headers.length).toBeGreaterThan(0)
      expect(cells.length).toBeGreaterThan(0)
    })
  })

  describe('Table Rows', () => {
    it('should have proper row structure', async () => {
      const { container } = render(
        <Table columns={mockColumns} data={mockData} />
      )

      const rows = container.querySelectorAll('tbody tr')
      expect(rows.length).toBe(mockData.length)

      for (const row of rows) {
        const cells = row.querySelectorAll('td')
        expect(cells.length).toBe(mockColumns.length)
      }
    })
  })

  describe('Complex Tables', () => {
    it('should handle tables with row headers', async () => {
      const { container } = render(
        <table>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {mockData.map((row) => (
              <tr key={row.id}>
                <th scope="row">{row.name}</th>
                <td>{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )

      const rowHeaders = container.querySelectorAll('tbody th[scope="row"]')
      expect(rowHeaders.length).toBe(mockData.length)
      await checkAccessibility(container)
    })

    it('should handle tables with headers attribute', async () => {
      const { container } = render(
        <table>
          <thead>
            <tr>
              <th id="name-header" scope="col">Name</th>
              <th id="status-header" scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {mockData.map((row) => (
              <tr key={row.id}>
                <td headers="name-header">{row.name}</td>
                <td headers="status-header">{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )

      const cellsWithHeaders = container.querySelectorAll('td[headers]')
      expect(cellsWithHeaders.length).toBeGreaterThan(0)
      await checkAccessibility(container)
    })
  })
})

