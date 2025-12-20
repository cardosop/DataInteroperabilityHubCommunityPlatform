/**
 * Data Quality API Service
 *
 * API functions for data quality run management operations:
 * - List DQ runs with filtering, sorting, and pagination
 * - Get single DQ run by ID
 * - Create/run DQ run
 * - Get DQ run results
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * DQ run status enum
 */
export type DQRunStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'

/**
 * DQ engine enum
 */
export type DQEngine = 'GREAT_EXPECTATIONS' | 'SODA'

/**
 * DQ overall status enum
 */
export type DQOverallStatus = 'PASS' | 'FAIL' | 'WARN' | 'UNKNOWN'

/**
 * DQ check status enum
 */
export type DQCheckStatus = 'PASS' | 'FAIL' | 'WARN' | 'UNKNOWN'

/**
 * DQ Run model
 */
export interface DQRun {
  id: string
  tenant: string
  asset?: string | null
  dataset?: string | null
  file?: string | null
  job: string
  profile_key: string
  engine: DQEngine
  status: DQRunStatus
  overall_status?: DQOverallStatus | null
  quality_score?: number | null
  checks_json?: Array<{
    name?: string
    type?: string
    status?: DQCheckStatus
    result?: Record<string, any>
    expectation?: string
    [key: string]: any
  }> | null
  details_json?: Record<string, any> | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

/**
 * List DQ runs query parameters
 */
export interface ListDQRunsParams {
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
   * Example: "-created_at"
   */
  ordering?: string
  /**
   * Filter by asset ID
   */
  asset_id?: string
  /**
   * Filter by dataset ID
   */
  dataset_id?: string
  /**
   * Filter by status (PENDING, RUNNING, SUCCEEDED, FAILED)
   */
  status?: DQRunStatus
  /**
   * Filter by date from (ISO 8601)
   */
  date_from?: string
  /**
   * Filter by date to (ISO 8601)
   */
  date_to?: string
}

/**
 * Create/run DQ run request payload
 */
export interface RunDQRunRequest {
  /**
   * Asset ID (optional, at least one of asset_id, dataset_id, or file_id required)
   */
  asset_id?: string | null
  /**
   * Dataset ID (optional, at least one of asset_id, dataset_id, or file_id required)
   */
  dataset_id?: string | null
  /**
   * File ID (optional, scan-only, at least one of asset_id, dataset_id, or file_id required)
   */
  file_id?: string | null
  /**
   * DQ profile key (optional, defaults to tenant default or platform default)
   */
  profile_key?: string
}

/**
 * DQ run results response
 */
export interface DQRunResults {
  dq_run_id: string
  overall_status: DQOverallStatus
  overall_score: number
  checks: Array<{
    name: string
    type: string
    status: DQCheckStatus
    result: Record<string, any>
    expectation?: string
    observed_value?: any
    expected_value?: any
    message?: string
    severity?: string
    [key: string]: any
  }>
  score_breakdown: {
    total_checks: number
    passed_checks: number
    failed_checks: number
    warning_checks: number
    pass_rate: number
    overall_score: number
    by_category: Record<
      string,
      {
        total: number
        passed: number
        failed: number
        warnings: number
      }
    >
  }
  trend_analysis?: {
    direction: 'IMPROVING' | 'DEGRADING' | 'STABLE'
    change_percentage?: number
    previous_value?: number
    current_value: number
    period_days?: number
    created_at: string
  }
  anomalies?: Array<{
    metric_type: string
    expected_value: number
    actual_value: number
    deviation: number
    severity: string
    detected_at: string
  }>
  recommendations?: Array<{
    check_name: string
    check_type: string
    message: string
    action: string
    priority: string
  }>
  metadata?: Record<string, any>
  started_at?: string | null
  completed_at?: string | null
}

/**
 * List DQ runs response
 */
export type ListDQRunsResponse = PaginatedResponse<DQRun>

/**
 * List DQ runs with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of DQ runs
 */
export async function listDQRuns(
  params?: ListDQRunsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListDQRunsResponse> {
  const queryParams: Record<string, any> = {
    page: params?.page,
    page_size: params?.page_size,
    ordering: params?.ordering,
    asset_id: params?.asset_id,
    dataset_id: params?.dataset_id,
    status: params?.status,
    date_from: params?.date_from,
    date_to: params?.date_to,
  }

  const response = await apiClient.get<ListDQRunsResponse>('/api/v1/dq/dq-runs/', {
    ...requestConfig,
    params: queryParams,
  })
  return response.data
}

/**
 * Get DQ run by ID
 *
 * @param id - DQ run UUID
 * @param config - Optional Axios request config
 * @returns DQ run details
 */
export async function getDQRun(id: string, config?: ExtendedFetchRequestInit): Promise<DQRun> {
  const response = await apiClient.get<DQRun>(`/api/v1/dq/dq-runs/${id}/`, config)
  return response.data
}

/**
 * Run/create a DQ run
 *
 * @param data - DQ run creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created DQ run
 */
export async function runDQRun(
  data: RunDQRunRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<DQRun> {
  const response = await apiClient.post<DQRun>('/api/v1/dq/dq-runs/', data, requestConfig)
  return response.data
}

/**
 * Get DQ run results
 *
 * @param id - DQ run UUID
 * @param requestConfig - Optional Axios request config
 * @returns DQ run results with detailed check information
 */
export async function getDQRunResults(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<DQRunResults> {
  const response = await apiClient.get<DQRunResults>(`/api/v1/dq/dq-runs/${id}/results/`, requestConfig)
  return response.data
}

