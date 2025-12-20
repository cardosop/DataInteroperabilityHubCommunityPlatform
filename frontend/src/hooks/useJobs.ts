/**
 * Job API Hooks
 *
 * React Query hooks for job management operations:
 * - useJobs() - List jobs query
 * - useJob(id) - Get single job query
 * - useJobStatus(id) - Get job status query with automatic polling
 *
 * These hooks provide:
 * - Automatic caching and background updates
 * - Request deduplication
 * - Automatic polling for job status until terminal state
 * - Error handling and retry logic
 * - Query invalidation on mutations
 */

import React from 'react'
import {
  useQuery,
  useQueryClient,
  UseQueryOptions,
  UseQueryResult,
} from '@tanstack/react-query'
import {
  listJobs,
  getJob,
  getJobStatus,
  type Job,
  type ListJobsParams,
  type ListJobsResponse,
  type JobStatus,
  isJobTerminal,
} from '@/lib/api/jobs'
import { queryKeys } from '@/lib/api/react-query'

/**
 * Polling configuration for job status
 */
export interface JobStatusPollingConfig {
  /**
   * Polling interval in milliseconds (default: 2000ms / 2 seconds)
   */
  interval?: number
  /**
   * Whether to enable polling (default: true)
   */
  enabled?: boolean
  /**
   * Maximum number of polling attempts (default: unlimited)
   * Set to limit polling duration
   */
  maxAttempts?: number
  /**
   * Callback when job reaches terminal state
   */
  onTerminal?: (job: Job) => void
  /**
   * Callback when job status changes
   */
  onStatusChange?: (status: JobStatus, previousStatus?: JobStatus) => void
}

/**
 * useJobs Hook
 *
 * Query hook for listing jobs with filtering, sorting, and pagination.
 *
 * @param params - Query parameters for filtering and pagination
 * @param options - Additional React Query options
 * @returns Query result with jobs list
 *
 * @example
 * ```tsx
 * function JobsList() {
 *   const { data, isLoading, error } = useJobs({
 *     page: 1,
 *     page_size: 20,
 *     status: 'RUNNING',
 *     type: 'DQ_RUN'
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *
 *   return (
 *     <div>
 *       {data?.results.map(job => (
 *         <JobCard key={job.id} job={job} />
 *       ))}
 *     </div>
 *   )
 * }
 * ```
 */
export function useJobs(
  params?: ListJobsParams,
  options?: Omit<UseQueryOptions<ListJobsResponse, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<ListJobsResponse, Error>({
    queryKey: queryKeys.jobs.list(params),
    queryFn: () => listJobs(params),
    ...options,
  })
}

/**
 * useJob Hook
 *
 * Query hook for getting a single job by ID.
 *
 * @param id - Job UUID
 * @param options - Additional React Query options
 * @returns Query result with job details
 *
 * @example
 * ```tsx
 * function JobDetail({ jobId }: { jobId: string }) {
 *   const { data: job, isLoading, error } = useJob(jobId)
 *
 *   if (isLoading) return <Loading />
 *   if (error) return <ErrorState error={error} />
 *   if (!job) return <NotFound />
 *
 *   return <JobDetails job={job} />
 * }
 * ```
 */
export function useJob(
  id: string | null | undefined,
  options?: Omit<UseQueryOptions<Job, Error>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Job, Error>({
    queryKey: queryKeys.jobs.detail(id!),
    queryFn: () => getJob(id!),
    enabled: !!id, // Only fetch if ID is provided
    ...options,
  })
}

/**
 * useJobStatus Hook
 *
 * Query hook for getting job status with automatic polling.
 * Polling automatically stops when the job reaches a terminal state
 * (COMPLETED, FAILED, or CANCELLED).
 *
 * @param id - Job UUID
 * @param pollingConfig - Polling configuration
 * @param options - Additional React Query options
 * @returns Query result with job status
 *
 * @example
 * ```tsx
 * function JobStatusIndicator({ jobId }: { jobId: string }) {
 *   const { data: job, isLoading } = useJobStatus(jobId, {
 *     interval: 3000, // Poll every 3 seconds
 *     onTerminal: (job) => {
 *       if (job.status === 'COMPLETED') {
 *         showSuccess('Job completed!')
 *       } else if (job.status === 'FAILED') {
 *         showError(`Job failed: ${job.error_message}`)
 *       }
 *     }
 *   })
 *
 *   if (isLoading) return <Loading />
 *   if (!job) return null
 *
 *   return (
 *     <div>
 *       <StatusBadge status={job.status} />
 *       {job.status === 'RUNNING' && <ProgressIndicator />}
 *     </div>
 *   )
 * }
 * ```
 */
export function useJobStatus(
  id: string | null | undefined,
  pollingConfig?: JobStatusPollingConfig,
  options?: Omit<UseQueryOptions<Job, Error>, 'queryKey' | 'queryFn' | 'refetchInterval'>
): UseQueryResult<Job, Error> {
  const queryClient = useQueryClient()
  const {
    interval = 2000, // Default: poll every 2 seconds
    enabled = true,
    maxAttempts,
    onTerminal,
    onStatusChange,
  } = pollingConfig || {}

  // Track previous status for change detection
  const previousStatusRef = React.useRef<JobStatus | undefined>()

  const queryResult = useQuery<Job, Error>({
    queryKey: queryKeys.jobs.status(id!),
    queryFn: () => getJobStatus(id!),
    enabled: !!id && enabled, // Only fetch if ID is provided and polling is enabled
    refetchInterval: (query) => {
      // Don't poll if job is not found or query is disabled
      if (!id || !enabled) {
        return false
      }

      // Get current job data from cache
      const jobData = query.state.data

      // If we have job data and it's in a terminal state, stop polling
      if (jobData && isJobTerminal(jobData.status)) {
        // Call onTerminal callback if provided
        if (onTerminal) {
          onTerminal(jobData)
        }
        return false // Stop polling
      }

      // Check max attempts if configured
      if (maxAttempts !== undefined) {
        const attemptCount = query.state.fetchFailureCount || 0
        if (attemptCount >= maxAttempts) {
          return false
        }
      }

      // Detect status changes
      if (jobData && onStatusChange) {
        const currentStatus = jobData.status
        const previousStatus = previousStatusRef.current
        if (previousStatus && previousStatus !== currentStatus) {
          onStatusChange(currentStatus, previousStatus)
        }
        previousStatusRef.current = currentStatus
      }

      // Continue polling
      return interval
    },
    ...options,
  })

  // Update previous status ref when data changes
  React.useEffect(() => {
    if (queryResult.data) {
      previousStatusRef.current = queryResult.data.status
    }
  }, [queryResult.data])

  return queryResult
}

