/**
 * JobCard Tests
 *
 * Comprehensive tests for the JobCard component covering:
 * - Job information display
 * - Status indicators
 * - Progress display
 * - Click handlers
 * - Error message display
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { JobCard } from '../JobCard'
import type { Job } from '@/lib/api/jobs'

const mockJob: Job = {
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
  details_json: {
    progress: 65,
    current_step: 'Validating data',
  },
  timeout_seconds: 3600,
  created_at: '2024-01-01T10:00:00Z',
  updated_at: '2024-01-01T10:05:00Z',
}

describe('JobCard', () => {
  describe('Rendering', () => {
    it('should render job type', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      expect(screen.getByText(/dq run/i)).toBeInTheDocument()
    })

    it('should render job status', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      expect(screen.getByText(/running/i)).toBeInTheDocument()
    })

    it('should render resource information', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      expect(screen.getByText(/dataset/i)).toBeInTheDocument()
      expect(screen.getByText(/dataset-123/i)).toBeInTheDocument()
    })

    it('should render created time', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      expect(screen.getByText(/ago/i)).toBeInTheDocument()
    })
  })

  describe('Status Display', () => {
    it('should display pending status', () => {
      const pendingJob = { ...mockJob, status: 'PENDING' as const }
      render(<JobCard job={pendingJob} />)

      expect(screen.getByText(/pending/i)).toBeInTheDocument()
    })

    it('should display completed status', () => {
      const completedJob = {
        ...mockJob,
        status: 'COMPLETED' as const,
        completed_at: '2024-01-01T10:10:00Z',
      }
      render(<JobCard job={completedJob} />)

      expect(screen.getByText(/completed/i)).toBeInTheDocument()
    })

    it('should display failed status with error message', () => {
      const failedJob = {
        ...mockJob,
        status: 'FAILED' as const,
        error_message: 'Job failed due to timeout',
        completed_at: '2024-01-01T10:10:00Z',
      }
      render(<JobCard job={failedJob} />)

      expect(screen.getByText(/failed/i)).toBeInTheDocument()
      expect(screen.getByText(/job failed due to timeout/i)).toBeInTheDocument()
    })

    it('should display cancelled status', () => {
      const cancelledJob = {
        ...mockJob,
        status: 'CANCELLED' as const,
        completed_at: '2024-01-01T10:10:00Z',
      }
      render(<JobCard job={cancelledJob} />)

      expect(screen.getByText(/cancelled/i)).toBeInTheDocument()
    })
  })

  describe('Progress Display', () => {
    it('should display progress when available', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      expect(screen.getByText(/65%/i)).toBeInTheDocument()
    })

    it('should display current step when available', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      expect(screen.getByText(/validating data/i)).toBeInTheDocument()
    })

    it('should not display progress when not available', () => {
      const jobWithoutProgress = {
        ...mockJob,
        details_json: null,
      }
      render(<JobCard job={jobWithoutProgress} />)

      expect(screen.queryByText(/%/i)).not.toBeInTheDocument()
    })
  })

  describe('Interactions', () => {
    it('should call onClick when card is clicked', () => {
      const handleClick = vi.fn()
      render(<JobCard job={mockJob} onClick={handleClick} />)

      fireEvent.click(screen.getByText(/dq run/i).closest('div')!)

      expect(handleClick).toHaveBeenCalledWith(mockJob)
    })

    it('should be clickable by default', () => {
      renderWithProviders(<JobCard job={mockJob} />)

      const card = screen.getByText(/dq run/i).closest('div')
      expect(card).toHaveStyle({ cursor: 'pointer' })
    })

    it('should not be clickable when clickable is false', () => {
      render(<JobCard job={mockJob} clickable={false} />)

      const card = screen.getByText(/dq run/i).closest('div')
      expect(card).not.toHaveStyle({ cursor: 'pointer' })
    })
  })
})

