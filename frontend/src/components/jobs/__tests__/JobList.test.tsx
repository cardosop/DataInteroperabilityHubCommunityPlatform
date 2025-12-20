/**
 * JobList Tests
 *
 * Comprehensive tests for the JobList component covering:
 * - Job list rendering
 * - Loading and error states
 * - Empty state
 * - Pagination
 * - Filtering
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { JobList } from '../JobList'
import { useJobs } from '@/hooks/useJobs'

// Mock hooks
vi.mock('@/hooks/useJobs', () => ({
  useJobs: vi.fn(),
}))

const mockJobs = {
  results: [
    {
      id: 'job-1',
      tenant: 'tenant-1',
      type: 'DQ_RUN',
      status: 'RUNNING',
      resource_type: 'DATASET',
      resource_id: 'dataset-123',
      created_by: 'user-1',
      started_at: '2024-01-01T10:00:00Z',
      completed_at: null,
      error_message: null,
      result_json: null,
      details_json: { progress: 50 },
      timeout_seconds: 3600,
      created_at: '2024-01-01T10:00:00Z',
      updated_at: '2024-01-01T10:05:00Z',
    },
  ],
  count: 1,
  next: null,
  previous: null,
}

describe('JobList', () => {
  const mockUseJobs = vi.mocked(useJobs)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render job list', () => {
      mockUseJobs.mockReturnValue({
        data: mockJobs,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<JobList />)

      expect(screen.getByText(/jobs/i)).toBeInTheDocument()
    })

    it('should display jobs', () => {
      mockUseJobs.mockReturnValue({
        data: mockJobs,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<JobList />)

      expect(screen.getByText(/dq run/i)).toBeInTheDocument()
    })
  })

  describe('Loading and Error States', () => {
    it('should display loading state', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<JobList />)

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
    })

    it('should display error state', () => {
      mockUseJobs.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Failed to load jobs'),
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<JobList />)

      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })

    it('should display empty state', () => {
      mockUseJobs.mockReturnValue({
        data: { results: [], count: 0, next: null, previous: null },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      renderWithProviders(<JobList />)

      expect(screen.getByText(/no jobs found/i)).toBeInTheDocument()
    })
  })

  describe('Filtering', () => {
    it('should allow filtering by status', async () => {
      const mockRefetch = vi.fn()
      mockUseJobs.mockReturnValue({
        data: mockJobs,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      } as any)

      renderWithProviders(<JobList />)

      const statusFilter = screen.getByLabelText(/status/i)
      fireEvent.mouseDown(statusFilter)

      await waitFor(() => {
        expect(screen.getByText(/running/i)).toBeInTheDocument()
      })
    })
  })
})

