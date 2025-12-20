/**
 * DatasetSchemaViewer Tests
 *
 * Comprehensive tests for the DatasetSchemaViewer component covering:
 * - Schema fields display
 * - Field information (name, type, nullable)
 * - Empty state when no schema
 * - Table rendering
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DatasetSchemaViewer } from '../DatasetSchemaViewer'
import type { DatasetSchema } from '@/lib/api/datasets'

const mockSchema: DatasetSchema = {
  fields: [
    { name: 'id', type: 'string', nullable: false },
    { name: 'name', type: 'string', nullable: true },
    { name: 'age', type: 'integer', nullable: false },
    { name: 'email', type: 'string', nullable: true },
  ],
}

describe('DatasetSchemaViewer', () => {
  beforeEach(() => {
    // Clear any mocks
  })

  describe('Rendering', () => {
    it('should render schema fields table', () => {
      render(<DatasetSchemaViewer schema={mockSchema} />)

      expect(screen.getByText(/field name/i)).toBeInTheDocument()
      expect(screen.getByText(/data type/i)).toBeInTheDocument()
      expect(screen.getByText(/nullable/i)).toBeInTheDocument()
    })

    it('should display all schema fields', () => {
      render(<DatasetSchemaViewer schema={mockSchema} />)

      expect(screen.getByText('id')).toBeInTheDocument()
      expect(screen.getByText('name')).toBeInTheDocument()
      expect(screen.getByText('age')).toBeInTheDocument()
      expect(screen.getByText('email')).toBeInTheDocument()
    })

    it('should display field types', () => {
      render(<DatasetSchemaViewer schema={mockSchema} />)

      expect(screen.getAllByText('string').length).toBeGreaterThan(0)
      expect(screen.getByText('integer')).toBeInTheDocument()
    })

    it('should display nullable status', () => {
      render(<DatasetSchemaViewer schema={mockSchema} />)

      // Should show Yes/No for nullable fields
      const nullableCells = screen.getAllByText(/yes|no/i)
      expect(nullableCells.length).toBeGreaterThan(0)
    })
  })

  describe('Empty State', () => {
    it('should show empty state when schema is null', () => {
      render(<DatasetSchemaViewer schema={null} />)

      expect(screen.getByText(/no schema available/i)).toBeInTheDocument()
    })

    it('should show empty state when schema has no fields', () => {
      render(<DatasetSchemaViewer schema={{ fields: [] }} />)

      expect(screen.getByText(/no fields/i)).toBeInTheDocument()
    })
  })

  describe('Field Information', () => {
    it('should correctly display nullable fields', () => {
      render(<DatasetSchemaViewer schema={mockSchema} />)

      // Find the row for 'name' field which is nullable
      const nameRow = screen.getByText('name').closest('tr')
      if (nameRow) {
        expect(nameRow.textContent).toContain('Yes')
      }
    })

    it('should correctly display non-nullable fields', () => {
      render(<DatasetSchemaViewer schema={mockSchema} />)

      // Find the row for 'id' field which is not nullable
      const idRow = screen.getByText('id').closest('tr')
      if (idRow) {
        expect(idRow.textContent).toContain('No')
      }
    })
  })

  describe('Props', () => {
    it('should accept custom title', () => {
      render(<DatasetSchemaViewer schema={mockSchema} title="Custom Schema Title" />)

      expect(screen.getByText('Custom Schema Title')).toBeInTheDocument()
    })

    it('should accept showTitle prop', () => {
      render(<DatasetSchemaViewer schema={mockSchema} showTitle={false} />)

      expect(screen.queryByText(/schema/i)).not.toBeInTheDocument()
    })
  })
})

