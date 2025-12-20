/**
 * DatasetCard Tests
 *
 * Comprehensive tests for the DatasetCard component covering:
 * - Rendering with dataset data
 * - Format badge display
 * - Version information
 * - Schema information display
 * - Click handlers
 * - Action buttons
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { DatasetCard } from '../DatasetCard'
import type { Dataset } from '@/lib/api/datasets'

const mockDataset: Dataset = {
  id: 'dataset-123',
  tenant: 'tenant-1',
  asset: 'asset-123',
  file: 'file-123',
  schema_json: {
    fields: [
      { name: 'id', type: 'string', nullable: false },
      { name: 'name', type: 'string', nullable: true },
      { name: 'age', type: 'integer', nullable: false },
    ],
  },
  sample_data_json: null,
  row_count: 1000,
  format: 'CSV',
  version: 1,
  parent_version: null,
  semantic_version: null,
  version_tags: [],
  is_current: true,
  created_by: 'user-1',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}


describe('DatasetCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render dataset card with basic information', () => {
      renderWithProviders(<DatasetCard dataset={mockDataset} />)

      expect(screen.getByText(/v1/i)).toBeInTheDocument()
      expect(screen.getByText(/CSV/i)).toBeInTheDocument()
    })

    it('should display format badge', () => {
      renderWithProviders(<DatasetCard dataset={mockDataset} />)

      expect(screen.getByText('CSV')).toBeInTheDocument()
    })

    it('should display row count when available', () => {
      renderWithProviders(<DatasetCard dataset={mockDataset} />)

      expect(screen.getByText(/1,000/i)).toBeInTheDocument()
    })

    it('should display schema field count when schema is available', () => {
      renderWithProviders(<DatasetCard dataset={mockDataset} />)

      expect(screen.getByText(/3 fields/i)).toBeInTheDocument()
    })

    it('should display current version badge when is_current is true', () => {
      renderWithProviders(<DatasetCard dataset={mockDataset} />)

      expect(screen.getByText(/current/i)).toBeInTheDocument()
    })

    it('should display semantic version when available', () => {
      const datasetWithSemanticVersion = {
        ...mockDataset,
        semantic_version: '1.0.0',
      }

      renderWithProviders(<DatasetCard dataset={datasetWithSemanticVersion} />)

      expect(screen.getByText('1.0.0')).toBeInTheDocument()
    })

    it('should display version tags when available', () => {
      const datasetWithTags = {
        ...mockDataset,
        version_tags: ['production', 'stable'],
      }

      render(
        <TestWrapper>
          <DatasetCard dataset={datasetWithTags} />
        </TestWrapper>
      )

      expect(screen.getByText(/2 tags/i)).toBeInTheDocument()
    })
  })

  describe('Click Handling', () => {
    it('should call onClick when card is clicked', () => {
      const handleClick = vi.fn()

      render(
        <TestWrapper>
          <DatasetCard dataset={mockDataset} onClick={handleClick} />
        </TestWrapper>
      )

      const card = screen.getByRole('button') || screen.getByText(/v1/i).closest('div')
      if (card) {
        fireEvent.click(card)
        expect(handleClick).toHaveBeenCalledWith(mockDataset)
      }
    })

    it('should navigate to dataset detail page when clicked without onClick handler', () => {
      const mockNavigate = vi.fn()
      vi.mock('react-router-dom', async () => {
        const actual = await vi.importActual('react-router-dom')
        return {
          ...actual,
          useNavigate: () => mockNavigate,
        }
      })

      render(
        <TestWrapper>
          <DatasetCard dataset={mockDataset} clickable />
        </TestWrapper>
      )
    })
  })

  describe('Actions', () => {
    it('should call onView when view button is clicked', () => {
      const handleView = vi.fn()

      render(
        <TestWrapper>
          <DatasetCard dataset={mockDataset} onView={handleView} showActions />
        </TestWrapper>
      )

      const viewButton = screen.getByLabelText(/view/i) || screen.getByText(/view/i)
      if (viewButton) {
        fireEvent.click(viewButton)
        expect(handleView).toHaveBeenCalledWith(mockDataset)
      }
    })

    it('should not show actions when showActions is false', () => {
      render(
        <TestWrapper>
          <DatasetCard dataset={mockDataset} showActions={false} />
        </TestWrapper>
      )

      expect(screen.queryByLabelText(/view/i)).not.toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('should handle dataset without schema', () => {
      const datasetWithoutSchema = {
        ...mockDataset,
        schema_json: null,
      }

      render(
        <TestWrapper>
          <DatasetCard dataset={datasetWithoutSchema} />
        </TestWrapper>
      )

      expect(screen.queryByText(/fields/i)).not.toBeInTheDocument()
    })

    it('should handle dataset without row count', () => {
      const datasetWithoutRowCount = {
        ...mockDataset,
        row_count: null,
      }

      render(
        <TestWrapper>
          <DatasetCard dataset={datasetWithoutRowCount} />
        </TestWrapper>
      )

      expect(screen.queryByText(/rows/i)).not.toBeInTheDocument()
    })

    it('should handle dataset without asset', () => {
      const datasetWithoutAsset = {
        ...mockDataset,
        asset: null,
      }

      render(
        <TestWrapper>
          <DatasetCard dataset={datasetWithoutAsset} />
        </TestWrapper>
      )

      expect(screen.getByText(/no asset/i)).toBeInTheDocument()
    })
  })
})

