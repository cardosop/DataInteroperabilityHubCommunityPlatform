/**
 * Platform Admin API Service
 *
 * API functions for platform administration operations:
 * - Get system metrics
 * - Get platform overview statistics
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'

/**
 * System metrics response
 * Prometheus-formatted metrics text
 */
export interface SystemMetrics {
  /**
   * Raw Prometheus metrics text
   */
  metrics: string
  /**
   * Timestamp when metrics were collected
   */
  timestamp: string
}

/**
 * Platform overview statistics
 */
export interface PlatformOverview {
  /**
   * Total number of tenants
   */
  total_tenants: number
  /**
   * Number of active tenants
   */
  active_tenants: number
  /**
   * Number of suspended tenants
   */
  suspended_tenants: number
  /**
   * Number of verified tenants (KYC)
   */
  verified_tenants: number
  /**
   * Total number of users across all tenants
   */
  total_users: number
  /**
   * Total number of assets across all tenants
   */
  total_assets: number
  /**
   * Total number of datasets across all tenants
   */
  total_datasets: number
  /**
   * Total number of active jobs
   */
  active_jobs: number
  /**
   * Total number of queued jobs
   */
  queued_jobs: number
  /**
   * System health status
   */
  system_health: 'healthy' | 'degraded' | 'unhealthy'
  /**
   * Timestamp when overview was generated
   */
  timestamp: string
}

/**
 * Get system metrics (Prometheus format)
 *
 * @param config - Optional Axios request config
 * @returns System metrics in Prometheus format
 */
export async function getSystemMetrics(config?: ExtendedFetchRequestInit): Promise<string> {
  const response = await apiClient.get<string>('/api/v1/observability/metrics/', {
    ...config,
    responseType: 'text',
  })
  return response.data
}

/**
 * Get platform overview statistics
 *
 * This aggregates data from multiple sources to provide a high-level view
 * of the platform status. Currently computed client-side from tenants list.
 * In the future, this could be a dedicated endpoint for better performance.
 *
 * Note: This function is currently a placeholder. The actual overview
 * will be computed in the component from the tenants list data.
 * For now, we return a basic structure that can be enhanced.
 *
 * @param config - Optional Axios request config
 * @returns Platform overview statistics
 */
export async function getPlatformOverview(config?: ExtendedFetchRequestInit): Promise<PlatformOverview> {
  // TODO: In the future, create a dedicated /api/v1/admin/overview/ endpoint
  // For now, return a basic structure - actual computation will be done client-side
  // from the tenants list and other available data
  return {
    total_tenants: 0,
    active_tenants: 0,
    suspended_tenants: 0,
    verified_tenants: 0,
    total_users: 0,
    total_assets: 0,
    total_datasets: 0,
    active_jobs: 0,
    queued_jobs: 0,
    system_health: 'healthy',
    timestamp: new Date().toISOString(),
  }
}
