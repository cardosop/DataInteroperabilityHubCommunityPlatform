/**
 * Job Hooks Tests
 *
 * Comprehensive tests for job API hooks covering:
 * - useJobs() - List jobs query
 * - useJob(id) - Get single job query
 * - useJobStatus(id) - Get job status query with polling
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import {
  useJobs,
  useJob,
  useJobStatus,
} from '../useJobs'
import * as jobsApi from '@/lib/api/jobs'
import { createHookWrapper } from './test-utils'

// Mock the jobs API
vi.mock('@/lib/api/jobs', () => ({
  listJobs: vi.fn(),
  getJob: vi.fn(),
  getJobStatus: vi.fn(),
  isJobTerminal: vi.fn((status) =>
    status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED'
  ),
}))

// Mock invalidateQueries
vi.mock('@/lib/api/react-query', async () => {
  const actual = await vi.importActual('@/lib/api/react-query')
  return {
    ...actual,
    invalidateQueries: vi.fn(),
  }
})

describe('Job Hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  describe('useJobs', () => {
    it('should fetch jobs list successfully', async () => {
      const mockJobs = {
        count: 2,
        page: 1,
        page_size: 50,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'job-1',
            tenant: 'tenant-1',
            type: 'DQ_RUN' as const,
            status: 'RUNNING' as const,
            resource_type: 'DATASET',
            resource_id: 'dataset-1',
            created_by: 'user-1',
            started_at: '2024-01-01T00:00:00Z',
            completed_at: null,
            error_message: null,
            result_json: null,
            details_json: {},
            timeout_seconds: 300,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
          {
            id: 'job-2',
            tenant: 'tenant-1',
            type: 'COMPLIANCE_RUN' as const,
            status: 'COMPLETED' as const,
            resource_type: 'ASSET',
            resource_id: 'asset-1',
            created_by: 'user-1',
            started_at: '2024-01-01T00:00:00Z',
            completed_at: '2024-01-01T00:05:00Z',
            error_message: null,
            result_json: { score: 95 },
            details_json: {},
            timeout_seconds: 300,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:05:00Z',
          },
        ],
      }

      vi.mocked(jobsApi.listJobs).mockResolvedValue(mockJobs)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJobs(), { wrapper })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(result.current.data).toEqual(mockJobs)
      expect(jobsApi.listJobs).toHaveBeenCalledWith(undefined, undefined)
    })

    it('should fetch jobs with filters', async () => {
      const params = {
        page: 1,
        page_size: 20,
        status: 'RUNNING' as const,
        type: 'DQ_RUN' as const,
      }

      const mockJobs = {
        count: 1,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'job-1',
            tenant: 'tenant-1',
            type: 'DQ_RUN' as const,
            status: 'RUNNING' as const,
            resource_type: 'DATASET',
            resource_id: 'dataset-1',
            created_by: 'user-1',
            started_at: '2024-01-01T00:00:00Z',
            completed_at: null,
            error_message: null,
            result_json: null,
            details_json: {},
            timeout_seconds: 300,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ],
      }

      vi.mocked(jobsApi.listJobs).mockResolvedValue(mockJobs)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJobs(params), { wrapper })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(result.current.data).toEqual(mockJobs)
      expect(jobsApi.listJobs).toHaveBeenCalledWith(params, undefined)
    })

    it('should handle error when fetching jobs fails', async () => {
      const error = new Error('Failed to fetch jobs')
      vi.mocked(jobsApi.listJobs).mockRejectedValue(error)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJobs(), { wrapper })

      await waitFor(() => expect(result.current.isError).toBe(true))

      expect(result.current.error).toEqual(error)
    })
  })

  describe('useJob', () => {
    it('should fetch single job successfully', async () => {
      const jobId = 'job-1'
      const mockJob = {
        id: jobId,
        tenant: 'tenant-1',
        type: 'DQ_RUN' as const,
        status: 'RUNNING' as const,
        resource_type: 'DATASET',
        resource_id: 'dataset-1',
        created_by: 'user-1',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        error_message: null,
        result_json: null,
        details_json: {},
        timeout_seconds: 300,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      vi.mocked(jobsApi.getJob).mockResolvedValue(mockJob)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJob(jobId), { wrapper })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(result.current.data).toEqual(mockJob)
      expect(jobsApi.getJob).toHaveBeenCalledWith(jobId, undefined)
    })

    it('should not fetch when id is null', () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJob(null), { wrapper })

      expect(result.current.isFetching).toBe(false)
      expect(jobsApi.getJob).not.toHaveBeenCalled()
    })

    it('should not fetch when id is undefined', () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJob(undefined), { wrapper })

      expect(result.current.isFetching).toBe(false)
      expect(jobsApi.getJob).not.toHaveBeenCalled()
    })

    it('should handle error when fetching job fails', async () => {
      const jobId = 'job-1'
      const error = new Error('Job not found')
      vi.mocked(jobsApi.getJob).mockRejectedValue(error)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJob(jobId), { wrapper })

      await waitFor(() => expect(result.current.isError).toBe(true))

      expect(result.current.error).toEqual(error)
    })
  })

  describe('useJobStatus', () => {
    it('should fetch job status successfully', async () => {
      const jobId = 'job-1'
      const mockJob = {
        id: jobId,
        tenant: 'tenant-1',
        type: 'DQ_RUN' as const,
        status: 'RUNNING' as const,
        resource_type: 'DATASET',
        resource_id: 'dataset-1',
        created_by: 'user-1',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        error_message: null,
        result_json: null,
        details_json: {},
        timeout_seconds: 300,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      vi.mocked(jobsApi.getJobStatus).mockResolvedValue(mockJob)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJobStatus(jobId), { wrapper })

      await waitFor(() => expect(result.current.isSuccess).toBe(true))

      expect(result.current.data).toEqual(mockJob)
      expect(jobsApi.getJobStatus).toHaveBeenCalledWith(jobId, undefined)
    })

    it('should poll job status when job is running', async () => {
      const jobId = 'job-1'
      const runningJob = {
        id: jobId,
        tenant: 'tenant-1',
        type: 'DQ_RUN' as const,
        status: 'RUNNING' as const,
        resource_type: 'DATASET',
        resource_id: 'dataset-1',
        created_by: 'user-1',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        error_message: null,
        result_json: null,
        details_json: {},
        timeout_seconds: 300,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      const completedJob = {
        ...runningJob,
        status: 'COMPLETED' as const,
        completed_at: '2024-01-01T00:05:00Z',
        result_json: { score: 95 },
        updated_at: '2024-01-01T00:05:00Z',
      }

      vi.mocked(jobsApi.getJobStatus)
        .mockResolvedValueOnce(runningJob)
        .mockResolvedValueOnce(runningJob)
        .mockResolvedValueOnce(completedJob)

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useJobStatus(jobId, { interval: 1000 }),
        { wrapper }
      )

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(result.current.data?.status).toBe('RUNNING')

      // Advance timer to trigger polling
      vi.advanceTimersByTime(1000)
      await waitFor(() => {
        expect(jobsApi.getJobStatus).toHaveBeenCalledTimes(2)
      })

      // Advance timer again
      vi.advanceTimersByTime(1000)
      await waitFor(() => {
        expect(jobsApi.getJobStatus).toHaveBeenCalledTimes(3)
        expect(result.current.data?.status).toBe('COMPLETED')
      })
    })

    it('should stop polling when job reaches terminal state', async () => {
      const jobId = 'job-1'
      const completedJob = {
        id: jobId,
        tenant: 'tenant-1',
        type: 'DQ_RUN' as const,
        status: 'COMPLETED' as const,
        resource_type: 'DATASET',
        resource_id: 'dataset-1',
        created_by: 'user-1',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: '2024-01-01T00:05:00Z',
        error_message: null,
        result_json: { score: 95 },
        details_json: {},
        timeout_seconds: 300,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:05:00Z',
      }

      vi.mocked(jobsApi.getJobStatus).mockResolvedValue(completedJob)

      const onTerminal = vi.fn()

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useJobStatus(jobId, { interval: 1000, onTerminal }),
        { wrapper }
      )

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(result.current.data?.status).toBe('COMPLETED')

      // Advance timer - polling should not continue
      vi.advanceTimersByTime(2000)
      await waitFor(() => {
        // Should only be called once since job is terminal
        expect(jobsApi.getJobStatus).toHaveBeenCalledTimes(1)
        expect(onTerminal).toHaveBeenCalledWith(completedJob)
      })
    })

    it('should call onStatusChange when status changes', async () => {
      const jobId = 'job-1'
      const pendingJob = {
        id: jobId,
        tenant: 'tenant-1',
        type: 'DQ_RUN' as const,
        status: 'PENDING' as const,
        resource_type: 'DATASET',
        resource_id: 'dataset-1',
        created_by: 'user-1',
        started_at: null,
        completed_at: null,
        error_message: null,
        result_json: null,
        details_json: {},
        timeout_seconds: 300,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      const runningJob = {
        ...pendingJob,
        status: 'RUNNING' as const,
        started_at: '2024-01-01T00:01:00Z',
        updated_at: '2024-01-01T00:01:00Z',
      }

      vi.mocked(jobsApi.getJobStatus)
        .mockResolvedValueOnce(pendingJob)
        .mockResolvedValueOnce(runningJob)

      const onStatusChange = vi.fn()

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useJobStatus(jobId, { interval: 1000, onStatusChange }),
        { wrapper }
      )

      await waitFor(() => expect(result.current.isSuccess).toBe(true))
      expect(result.current.data?.status).toBe('PENDING')

      // Advance timer to trigger polling and status change
      vi.advanceTimersByTime(1000)
      await waitFor(() => {
        expect(result.current.data?.status).toBe('RUNNING')
        expect(onStatusChange).toHaveBeenCalledWith('RUNNING', 'PENDING')
      })
    })

    it('should not poll when enabled is false', async () => {
      const jobId = 'job-1'
      const mockJob = {
        id: jobId,
        tenant: 'tenant-1',
        type: 'DQ_RUN' as const,
        status: 'RUNNING' as const,
        resource_type: 'DATASET',
        resource_id: 'dataset-1',
        created_by: 'user-1',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: null,
        error_message: null,
        result_json: null,
        details_json: {},
        timeout_seconds: 300,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      vi.mocked(jobsApi.getJobStatus).mockResolvedValue(mockJob)

      const wrapper = createHookWrapper()
      const { result } = renderHook(
        () => useJobStatus(jobId, { enabled: false, interval: 1000 }),
        { wrapper }
      )

      // Should not fetch when disabled
      expect(result.current.isFetching).toBe(false)
      expect(jobsApi.getJobStatus).not.toHaveBeenCalled()
    })

    it('should not fetch when id is null', () => {
      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJobStatus(null), { wrapper })

      expect(result.current.isFetching).toBe(false)
      expect(jobsApi.getJobStatus).not.toHaveBeenCalled()
    })

    it('should handle error when fetching job status fails', async () => {
      const jobId = 'job-1'
      const error = new Error('Job not found')
      vi.mocked(jobsApi.getJobStatus).mockRejectedValue(error)

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useJobStatus(jobId), { wrapper })

      await waitFor(() => expect(result.current.isError).toBe(true))

      expect(result.current.error).toEqual(error)
    })
  })
})

