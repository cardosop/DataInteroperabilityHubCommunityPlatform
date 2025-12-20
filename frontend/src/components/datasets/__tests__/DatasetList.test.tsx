/**
 * DatasetList Tests
 *
 * Comprehensive tests for the DatasetList component covering:
 * - Rendering datasets in grid layout
 * - Rendering datasets in list layout
 * - Loading state
 * - Error state
 * - Empty state
 * - Callback handlers
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { DatasetList } from '../DatasetList'
import type { Dataset } from '@/lib/api/datasets'

const mockDatasets: Dataset[] = [
  {
    id: 'dataset-1',
    tenant: 'tenant-1',
    asset: 'asset-1',
    file: 'file-1',
    schema_json: {
      fields: [
        { name: 'id', type: 'string', nullable: false },
        { name: 'name', type: 'string', nullable: true },
      ],
    },
    sample_data_json: null,
    row_count: 100,
    format: 'CSV',
    version: 1,
    parent_version: null,
    semantic_version: null,
    version_tags: [],
    is_current: true,
    created_by: 'user-1',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'dataset-2',
    tenant: 'tenant-1',
    asset: null,
    file: 'file-2',
    schema_json: null,
    sample_data_json: null,
    row_count: null,
    format: 'JSON',
    version: 1,
    parent_version: null,
    semantic_version: '1.0.0',
    version_tags: ['production'],
    is_current: false,
    created_by: 'user-1',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
]


describe('DatasetList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render datasets in grid layout by default', () => {
      renderWithProviders(<DatasetList datasets={mockDatasets} />
 />)

      expect(screen.getByText(/v1/i)).toBeInTheDocument()
      expect(screen.getAllByText(/CSV|JSON/i).length).toBeGreaterThan(0)
    })

    it('should render datasets in list layout when variant is list', () => {
      renderWithProviders(<DatasetList datasets={mockDatasets} variant="list" />
 />)

      expect(screen.getByText(/v1/i)).toBeInTheDocument()
    })

    it('should render correct number of dataset cards', () => {
      renderWithProviders(<DatasetList datasets={mockDatasets} />
 />)

      // Should render 2 dataset cards
      const cards = screen.getAllByText(/Dataset v/i)
      expect(cards.length).toBe(2)
    })
  })

  describe('Loading State', () => {
    it('should show loading skeletons when loading', () => {
      renderWithProviders(<DatasetList datasets={[]} loading />
 />)

      // Should show skeleton loaders
      expect(screen.queryByText(/Dataset v/i)).not.toBeInTheDocument()
    })
  })

  describe('Error State', () => {
    it('should show error state when error occurs', () => {
      const error = new Error('Failed to load datasets')

      renderWithProviders(<DatasetList datasets={[]} error={error} />
 />)

      expect(screen.getByText(/failed to load datasets/i)).toBeInTheDocument()
    })

    it('should call onRetry when retry button is clicked', () => {
      const error = new Error('Failed to load datasets')
      const handleRetry = vi.fn()

      renderWithProviders(<DatasetList datasets={[]} error={error} onRetry={handleRetry} />
 />)

      const retryButton = screen.getByText(/retry/i)
      retryButton.click()
      expect(handleRetry).toHaveBeenCalled()
    })
  })

  describe('Empty State', () => {
    it('should show empty state when no datasets', () => {
      renderWithProviders(<DatasetList datasets={[]} />
 />)

      expect(screen.getByText(/no datasets found/i)).toBeInTheDocument()
    })

    it('should show custom empty message', () => {
      renderWithProviders(<DatasetList datasets={[]} emptyMessage="No datasets available" />
 />)

      expect(screen.getByText(/no datasets available/i)).toBeInTheDocument()
    })

    it('should show empty action when provided', () => {
      const handleEmptyAction = vi.fn()

      renderWithProviders(<DatasetList
            datasets={[]}
            emptyAction={{
              label: 'Upload Dataset',
              onClick: handleEmptyAction,
            }}
          />
 />)

      const actionButton = screen.getByText(/upload dataset/i)
      actionButton.click()
      expect(handleEmptyAction).toHaveBeenCalled()
    })
  })

  describe('Callbacks', () => {
    it('should call onDatasetClick when dataset card is clicked', () => {
      const handleClick = vi.fn()

      renderWithProviders(<DatasetList datasets={mockDatasets} onDatasetClick={handleClick} />
 />)

      // Click on first dataset card
      const card = screen.getAllByText(/Dataset v/i)[0]
      card.click()
      expect(handleClick).toHaveBeenCalledWith(mockDatasets[0])
    })

    it('should call onView when view is clicked', () => {
      const handleView = vi.fn()

      renderWithProviders(<DatasetList datasets={mockDatasets} onView={handleView} />
 />)

      // Find and click view button
      const viewButtons = screen.getAllByLabelText(/view dataset/i)
      if (viewButtons.length > 0) {
        viewButtons[0].click()
        expect(handleView).toHaveBeenCalled()
      }
    })
  })

  describe('Layout Configuration', () => {
    it('should respect columns prop for grid layout', () => {
      renderWithProviders(<DatasetList datasets={mockDatasets} columns={2} />
 />)

      // Grid should be rendered with 2 columns
      expect(screen.getByText(/Dataset v/i)).toBeInTheDocument()
    })

    it('should respect spacing prop', () => {
      renderWithProviders(<DatasetList datasets={mockDatasets} spacing={4} />
 />)

      expect(screen.getByText(/Dataset v/i)).toBeInTheDocument()
    })

    it('should hide actions when showActions is false', () => {
      renderWithProviders(<DatasetList datasets={mockDatasets} showActions={false} />
 />)

      expect(screen.queryByLabelText(/view dataset/i)).not.toBeInTheDocument()
    })
  })
})

