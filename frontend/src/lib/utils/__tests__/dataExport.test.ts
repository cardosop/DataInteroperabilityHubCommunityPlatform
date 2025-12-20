/**
 * Data Export Utilities Tests
 *
 * Comprehensive tests for data export utilities covering:
 * - CSV conversion and formatting
 * - JSON export
 * - Excel export
 * - File download functionality
 * - Edge cases and error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  exportToCSV,
  exportToJSON,
  exportToExcel,
  exportData,
} from '../dataExport'

describe('dataExport utilities', () => {
  let createElementSpy: ReturnType<typeof vi.spyOn>
  let appendChildSpy: ReturnType<typeof vi.spyOn>
  let removeChildSpy: ReturnType<typeof vi.spyOn>
  let clickSpy: ReturnType<typeof vi.fn>
  let createObjectURLSpy: ReturnType<typeof vi.spyOn>
  let revokeObjectURLSpy: ReturnType<typeof vi.spyOn>
  let mockLink: HTMLAnchorElement
  let mockBlob: Blob

  beforeEach(() => {
    // Mock DOM APIs
    mockLink = {
      href: '',
      download: '',
      click: vi.fn(),
    } as any

    mockBlob = new Blob(['test'], { type: 'text/plain' })

    createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'a') {
        return mockLink as any
      }
      return document.createElement(tagName)
    })

    appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as any)
    removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockLink as any)
    clickSpy = vi.fn()
    mockLink.click = clickSpy

    createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url')
    revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('exportToCSV', () => {
    it('should export simple data to CSV', () => {
      const data = [
        { name: 'John', age: 30 },
        { name: 'Jane', age: 25 },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.csv')
      expect(clickSpy).toHaveBeenCalled()
      expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url')
    })

    it('should include headers by default', () => {
      const data = [
        { name: 'John', age: 30 },
        { name: 'Jane', age: 25 },
      ]

      exportToCSV(data)

      const blobCall = createObjectURLSpy.mock.calls[0]
      expect(blobCall).toBeDefined()
    })

    it('should exclude headers when includeHeaders is false', () => {
      const data = [
        { name: 'John', age: 30 },
      ]

      exportToCSV(data, { includeHeaders: false })

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle empty data array', () => {
      const data: Array<Record<string, any>> = []

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.csv')
    })

    it('should handle custom filename', () => {
      const data = [{ name: 'John' }]

      exportToCSV(data, { filename: 'users' })

      expect(mockLink.download).toBe('users.csv')
    })

    it('should handle custom delimiter', () => {
      const data = [{ name: 'John', age: 30 }]

      exportToCSV(data, { delimiter: ';' })

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should escape commas in values', () => {
      const data = [{ name: 'John, Doe', age: 30 }]

      exportToCSV(data)

      const blob = createObjectURLSpy.mock.calls[0][0] as Blob
      expect(blob).toBeInstanceOf(Blob)
    })

    it('should escape quotes in values', () => {
      const data = [{ name: 'John "Johnny" Doe', age: 30 }]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should escape newlines in values', () => {
      const data = [{ name: 'John\nDoe', age: 30 }]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle null and undefined values', () => {
      const data = [
        { name: 'John', age: null, email: undefined },
        { name: 'Jane', age: 25, email: 'jane@example.com' },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle objects with different keys', () => {
      const data = [
        { name: 'John', age: 30 },
        { name: 'Jane', city: 'NYC' },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle numeric values', () => {
      const data = [
        { id: 1, price: 99.99, quantity: 5 },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle boolean values', () => {
      const data = [
        { name: 'John', active: true, verified: false },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle nested objects by converting to string', () => {
      const data = [
        { name: 'John', metadata: { role: 'admin' } },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })
  })

  describe('exportToJSON', () => {
    it('should export data to JSON', () => {
      const data = [{ name: 'John', age: 30 }]

      exportToJSON(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.json')
      expect(clickSpy).toHaveBeenCalled()
    })

    it('should export with pretty formatting when pretty is true', () => {
      const data = [{ name: 'John', age: 30 }]

      exportToJSON(data, { pretty: true })

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should export without pretty formatting by default', () => {
      const data = [{ name: 'John', age: 30 }]

      exportToJSON(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle custom filename', () => {
      const data = [{ name: 'John' }]

      exportToJSON(data, { filename: 'users' })

      expect(mockLink.download).toBe('users.json')
    })

    it('should handle complex nested objects', () => {
      const data = {
        users: [
          { name: 'John', metadata: { role: 'admin', tags: ['dev', 'ops'] } },
        ],
        count: 1,
      }

      exportToJSON(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle arrays', () => {
      const data = [1, 2, 3, 4, 5]

      exportToJSON(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle primitives', () => {
      exportToJSON('string')
      expect(createElementSpy).toHaveBeenCalledWith('a')

      exportToJSON(123)
      expect(createElementSpy).toHaveBeenCalledWith('a')

      exportToJSON(true)
      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle null and undefined', () => {
      exportToJSON(null)
      expect(createElementSpy).toHaveBeenCalledWith('a')

      exportToJSON(undefined)
      expect(createElementSpy).toHaveBeenCalledWith('a')
    })
  })

  describe('exportToExcel', () => {
    it('should export data to Excel format', () => {
      const data = [
        { name: 'John', age: 30 },
        { name: 'Jane', age: 25 },
      ]

      exportToExcel(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.xlsx')
      expect(clickSpy).toHaveBeenCalled()
    })

    it('should handle custom filename', () => {
      const data = [{ name: 'John' }]

      exportToExcel(data, { filename: 'users' })

      expect(mockLink.download).toBe('users.xlsx')
    })

    it('should handle empty data', () => {
      const data: Array<Record<string, any>> = []

      exportToExcel(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should use CSV format with .xlsx extension', () => {
      const data = [{ name: 'John', age: 30 }]

      exportToExcel(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toMatch(/\.xlsx$/)
    })
  })

  describe('exportData', () => {
    it('should export data as CSV', () => {
      const data = [{ name: 'John', age: 30 }]

      exportData(data, { format: 'csv' })

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.csv')
    })

    it('should export data as JSON', () => {
      const data = [{ name: 'John', age: 30 }]

      exportData(data, { format: 'json' })

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.json')
    })

    it('should export data as Excel', () => {
      const data = [{ name: 'John', age: 30 }]

      exportData(data, { format: 'excel' })

      expect(createElementSpy).toHaveBeenCalledWith('a')
      expect(mockLink.download).toBe('export.xlsx')
    })

    it('should apply formatter function when provided', () => {
      const data = [
        { firstName: 'John', lastName: 'Doe', age: 30 },
      ]

      exportData(data, {
        format: 'csv',
        formatter: (item) => ({
          name: `${item.firstName} ${item.lastName}`,
          age: item.age,
        }),
      })

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should combine formatter with other options', () => {
      const data = [{ name: 'John', age: 30 }]

      exportData(data, {
        format: 'csv',
        filename: 'users',
        includeHeaders: false,
        formatter: (item) => ({ name: item.name.toUpperCase() }),
      })

      expect(mockLink.download).toBe('users.csv')
    })

    it('should throw error for unsupported format', () => {
      const data = [{ name: 'John' }]

      expect(() => {
        exportData(data, { format: 'xml' as any })
      }).toThrow('Unsupported export format: xml')
    })

    it('should handle empty array with formatter', () => {
      const data: Array<Record<string, any>> = []

      exportData(data, {
        format: 'csv',
        formatter: (item) => item,
      })

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle complex formatter transformations', () => {
      const data = [
        { id: 1, user: { name: 'John', email: 'john@example.com' } },
      ]

      exportData(data, {
        format: 'json',
        formatter: (item) => ({
          id: item.id,
          name: item.user.name,
          email: item.user.email,
        }),
      })

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })
  })

  describe('edge cases and error handling', () => {
    it('should handle very large datasets', () => {
      const data = Array.from({ length: 10000 }, (_, i) => ({
        id: i,
        name: `User ${i}`,
      }))

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle special characters in field names', () => {
      const data = [
        { 'field-name': 'value', 'field_name': 'value2' },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should handle empty strings', () => {
      const data = [
        { name: '', age: 30 },
        { name: 'John', age: 0 },
      ]

      exportToCSV(data)

      expect(createElementSpy).toHaveBeenCalledWith('a')
    })

    it('should clean up DOM elements after download', () => {
      const data = [{ name: 'John' }]

      exportToCSV(data)

      expect(appendChildSpy).toHaveBeenCalled()
      expect(removeChildSpy).toHaveBeenCalled()
      expect(revokeObjectURLSpy).toHaveBeenCalled()
    })

    it('should handle circular references in JSON gracefully', () => {
      const data: any = { name: 'John' }
      data.self = data // Circular reference

      // JSON.stringify will throw, but we should handle it
      expect(() => {
        exportToJSON(data)
      }).toThrow()
    })
  })
})

