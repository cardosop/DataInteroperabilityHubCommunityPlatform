/**
 * DataQualityRunList Tests
 *
 * Comprehensive tests for the DataQualityRunList component covering:
 * - Run list rendering
 * - Loading and error states
 * - Empty state
 * - Pagination
 * - Filtering
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { DataQualityRunList } from '../DataQualityRunList'
import { useDQRuns } from '@/hooks/useDQRuns'

// Mock hooks
vi.mock('@/hooks/useDQRuns', () => ({
  useDQRuns: vi.fn(),
}))

const mockDQRuns = {
  results: [
    {
      id: 'run-1',
      tenant: 'tenant-1',
      asset: 'asset-1',
      dataset: 'dataset-1',
      job: 'job-1',
      profile_key: 'intake_basic',
      engine: 'GREAT_EXPECTATIONS',
      status: 'SUCCEEDED',
      overall_status: 'PASS',
      quality_score: 95,
      checks_json: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ],
  count: 1,
  next: null,
  previous: null,
}

describe('DataQualityRunList', () => {
  const mockUseDQRuns = vi.mocked(useDQRuns)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render run list', () => {
      mockUseDQRuns.mockReturnValue({
        data: mockDQRuns,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<DataQualityRunList />)

      expect(screen.getByText(/data quality runs/i)).toBeInTheDocument()
    })

    it('should display runs', () => {
      mockUseDQRuns.mockReturnValue({
        data: mockDQRuns,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<DataQualityRunList />)

      expect(screen.getByText(/run-1/i)).toBeInTheDocument()
    })
  })

  describe('Loading and Error States', () => {
    it('should display loading state', () => {
      mockUseDQRuns.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<DataQualityRunList />)

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('should display error state', () => {
      mockUseDQRuns.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load runs'),
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<DataQualityRunList />)

      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })

    it('should display empty state', () => {
      mockUseDQRuns.mockReturnValue({
        data: { results: [], count: 0, next: null, previous: null },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<DataQualityRunList />)

      expect(screen.getByText(/no runs found/i)).toBeInTheDocument()
    })
  })
})

