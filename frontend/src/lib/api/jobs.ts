/**
 * Job API Service
 *
 * API functions for job management operations:
 * - List jobs with filtering and pagination
 * - Get single job by ID
 * - Get job status (for polling)
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Job type enum
 */
export type JobType =
  | 'DQ_RUN'
  | 'COMPLIANCE_RUN'
  | 'CONTRACT_VALIDATION'
  | 'SEMANTIC_MAPPING'
  | 'CONTRACT_MIGRATION'
  | 'SCHEDULED_INGESTION'
  | 'RETENTION_POLICY_ENFORCEMENT'
  | 'SEARCH_INDEX_UPDATE'

/**
 * Job status enum
 */
export type JobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'

/**
 * Job model
 */
export interface Job {
  id: string
  tenant: string | null
  type: JobType
  status: JobStatus
  resource_type: string
  resource_id: string
  created_by: string | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  result_json: Record<string, any> | null
  details_json: Record<string, any> | null
  timeout_seconds: number | null
  created_at: string
  updated_at: string
}

/**
 * List jobs query parameters
 */
export interface ListJobsParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 50, max: 100)
   */
  page_size?: number
  /**
   * Sort fields (comma-separated, prefix with `-` for descending)
   * Example: "-created_at,status"
   */
  ordering?: string
  /**
   * Filter by job type
   */
  type?: JobType
  /**
   * Filter by job status
   */
  status?: JobStatus
  /**
   * Search in type, status, resource_type
   */
  search?: string
}

/**
 * List jobs response
 */
export type ListJobsResponse = PaginatedResponse<Job>

/**
 * Check if job status is terminal (job is finished)
 *
 * @param status - Job status
 * @returns True if job is in a terminal state
 */
export function isJobTerminal(status: JobStatus): boolean {
  return status === 'COMPLETED' || status === 'FAILED' || status === 'CANCELLED'
}

/**
 * Check if job is currently running
 *
 * @param status - Job status
 * @returns True if job is running
 */
export function isJobRunning(status: JobStatus): boolean {
  return status === 'RUNNING'
}

/**
 * Check if job can be cancelled
 *
 * @param status - Job status
 * @returns True if job can be cancelled
 */
export function canCancelJob(status: JobStatus): boolean {
  return status === 'PENDING' || status === 'RUNNING'
}

/**
 * List jobs with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of jobs
 */
export async function listJobs(
  params?: ListJobsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListJobsResponse> {
  const response = await apiClient.get<ListJobsResponse>(
    '/api/v1/jobs/jobs/',
    {
      ...requestConfig,
      params: {
        page: params?.page,
        page_size: params?.page_size,
        ordering: params?.ordering,
        type: params?.type,
        status: params?.status,
        search: params?.search,
      },
    }
  )
  return response.data
}

/**
 * Get job by ID
 *
 * @param id - Job UUID
 * @param requestConfig - Optional Axios request config
 * @returns Job details
 */
export async function getJob(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Job> {
  const response = await apiClient.get<Job>(
    `/api/v1/jobs/jobs/${id}/`,
    requestConfig
  )
  return response.data
}

/**
 * Get job status (lightweight endpoint for polling)
 * This is the same as getJob but semantically indicates it's for status polling
 *
 * @param id - Job UUID
 * @param requestConfig - Optional Axios request config
 * @returns Job with current status
 */
export async function getJobStatus(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<Job> {
  // For now, use the same endpoint as getJob
  // In the future, this could be a lightweight status-only endpoint
  return getJob(id, requestConfig)
}

