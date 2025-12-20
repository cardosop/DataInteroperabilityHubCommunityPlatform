/**
 * Audit API Service
 *
 * API functions for audit event operations:
 * - List audit events with filtering
 * - Get single audit event by ID
 * - Export audit events
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * Audit event action types
 */
export type AuditAction =
  | 'ASSET_CREATED'
  | 'ASSET_UPDATED'
  | 'ASSET_DELETED'
  | 'ASSET_ACTIVATED'
  | 'CONTRACT_CREATED'
  | 'CONTRACT_UPDATED'
  | 'CONTRACT_DELETED'
  | 'CONTRACT_VALIDATED'
  | 'DATASET_CREATED'
  | 'DATASET_UPDATED'
  | 'DATASET_DELETED'
  | 'USER_CREATED'
  | 'USER_UPDATED'
  | 'USER_DELETED'
  | string // Allow other action types

/**
 * Resource types
 */
export type ResourceType = 'ASSET' | 'CONTRACT' | 'DATASET' | 'USER' | 'JOB' | string

/**
 * Audit event model
 */
export interface AuditEvent {
  id: string
  tenant: string
  resource_type: ResourceType
  resource_id: string
  action: AuditAction
  actor_user_id: string | null
  actor_user_email: string | null
  actor_user_name: string | null
  metadata: Record<string, any> | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
}

/**
 * List audit events query parameters
 */
export interface ListAuditEventsParams {
  /**
   * Page number (1-indexed)
   */
  page?: number
  /**
   * Number of items per page (default: 50, max: 100)
   */
  page_size?: number
  /**
   * Filter by resource type (ASSET, CONTRACT, DATASET, etc.)
   */
  resource_type?: ResourceType
  /**
   * Filter by resource ID
   */
  resource_id?: string
  /**
   * Filter by action type
   */
  action?: AuditAction
  /**
   * Filter by actor user ID
   */
  actor_user_id?: string
  /**
   * Start date (ISO 8601 format)
   */
  start_date?: string
  /**
   * End date (ISO 8601 format)
   */
  end_date?: string
  /**
   * Sort fields (comma-separated, prefix with `-` for descending)
   * Example: "-created_at"
   */
  ordering?: string
}

/**
 * List audit events response
 */
export type ListAuditEventsResponse = PaginatedResponse<AuditEvent>

/**
 * List audit events with filtering
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of audit events
 */
export async function listAuditEvents(
  params?: ListAuditEventsParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListAuditEventsResponse> {
  const response = await apiClient.get<ListAuditEventsResponse>(
    '/api/v1/audit/audit-events/',
    {
      ...requestConfig,
      params: {
        page: params?.page,
        page_size: params?.page_size,
        resource_type: params?.resource_type,
        resource_id: params?.resource_id,
        action: params?.action,
        actor_user_id: params?.actor_user_id,
        start_date: params?.start_date,
        end_date: params?.end_date,
        ordering: params?.ordering || '-created_at',
      },
    }
  )
  return response.data
}

/**
 * Get audit event by ID
 *
 * @param id - Audit event UUID
 * @param requestConfig - Optional Axios request config
 * @returns Audit event details
 */
export async function getAuditEvent(
  id: string,
  requestConfig?: ExtendedFetchRequestInit
): Promise<AuditEvent> {
  const response = await apiClient.get<AuditEvent>(
    `/api/v1/audit/audit-events/${id}/`,
    requestConfig
  )
  return response.data
}

