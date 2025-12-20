/**
 * User API Service
 *
 * API functions for user management operations:
 * - List users with filtering and pagination
 * - Get single user by ID
 * - Create user
 * - Update user
 * - Delete user
 * - Invite user
 * - Assign/remove roles
 */

import type { ExtendedFetchRequestInit } from 'axios'
import { apiClient } from './client'
import { PaginatedResponse } from './responses'

/**
 * User status enum
 */
export type UserStatus = 'ACTIVE' | 'INVITED' | 'DISABLED' | 'SUSPENDED'

/**
 * Role model
 */
export interface Role {
  id: string
  tenant?: string | null
  name: string
  description?: string | null
  created_at: string
  updated_at: string
}

/**
 * User model
 */
export interface User {
  id: string
  tenant?: string | null
  email: string
  display_name?: string | null
  status: UserStatus
  is_platform_admin: boolean
  roles?: Role[]
  created_at: string
  updated_at: string
}

/**
 * List users query parameters
 */
export interface ListUsersParams {
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
   * Filter by status (ACTIVE, INVITED, DISABLED, SUSPENDED)
   */
  status?: UserStatus
}

/**
 * Create user request payload
 */
export interface CreateUserRequest {
  email: string
  display_name?: string
  password?: string
  role_ids?: string[]
  send_invitation?: boolean
  status?: UserStatus
}

/**
 * Update user request payload
 */
export interface UpdateUserRequest {
  display_name?: string
  status?: UserStatus
}

/**
 * Invite user request payload
 */
export interface InviteUserRequest {
  email: string
  display_name?: string
  role_ids?: string[]
}

/**
 * Assign/remove role request payload
 */
export interface UserRoleAssignmentRequest {
  role_id: string
  action: 'assign' | 'remove'
}

/**
 * List users response
 */
export type ListUsersResponse = PaginatedResponse<User>

/**
 * List roles response
 */
export type ListRolesResponse = PaginatedResponse<Role>

/**
 * List users with filtering, sorting, and pagination
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of users
 */
export async function listUsers(
  params?: ListUsersParams,
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListUsersResponse> {
  const queryParams: Record<string, any> = {
    page: params?.page,
    page_size: params?.page_size,
    ordering: params?.ordering,
    status: params?.status,
  }

  const response = await apiClient.get<ListUsersResponse>('/api/v1/users/users/', {
    ...requestConfig,
    params: queryParams,
  })
  return response.data
}

/**
 * Get user by ID
 *
 * @param id - User UUID
 * @param config - Optional Axios request config
 * @returns User details
 */
export async function getUser(id: string, config?: ExtendedFetchRequestInit): Promise<User> {
  const response = await apiClient.get<User>(`/api/v1/users/users/${id}/`, config)
  return response.data
}

/**
 * Create user
 *
 * @param data - User creation data
 * @param requestConfig - Optional Axios request config
 * @returns Created user
 */
export async function createUser(
  data: CreateUserRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<User> {
  const response = await apiClient.post<User>('/api/v1/users/users/', data, requestConfig)
  return response.data
}

/**
 * Update user
 *
 * @param id - User UUID
 * @param data - User update data
 * @param requestConfig - Optional Axios request config
 * @returns Updated user
 */
export async function updateUser(
  id: string,
  data: UpdateUserRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<User> {
  const response = await apiClient.patch<User>(`/api/v1/users/users/${id}/`, data, requestConfig)
  return response.data
}

/**
 * Delete user
 *
 * @param id - User UUID
 * @param requestConfig - Optional Axios request config
 */
export async function deleteUser(id: string, requestConfig?: ExtendedFetchRequestInit): Promise<void> {
  await apiClient.delete(`/api/v1/users/users/${id}/`, requestConfig)
}

/**
 * Invite user
 *
 * @param data - Invitation data
 * @param requestConfig - Optional Axios request config
 * @returns Invited user
 */
export async function inviteUser(
  data: InviteUserRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<User> {
  const response = await apiClient.post<User>('/api/v1/users/users/invite/', data, requestConfig)
  return response.data
}

/**
 * Assign or remove role from user
 *
 * @param userId - User UUID
 * @param data - Role assignment data
 * @param requestConfig - Optional Axios request config
 * @returns Updated user
 */
export async function assignUserRole(
  userId: string,
  data: UserRoleAssignmentRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<User> {
  const response = await apiClient.post<User>(
    `/api/v1/users/users/${userId}/roles/`,
    data,
    requestConfig
  )
  return response.data
}

/**
 * List roles
 *
 * @param params - Query parameters for filtering and pagination
 * @param requestConfig - Optional Axios request config
 * @returns Paginated list of roles
 */
export async function listRoles(
  params?: {
    page?: number
    page_size?: number
    ordering?: string
  },
  requestConfig?: ExtendedFetchRequestInit
): Promise<ListRolesResponse> {
  const queryParams: Record<string, any> = {
    page: params?.page,
    page_size: params?.page_size,
    ordering: params?.ordering,
  }

  const response = await apiClient.get<ListRolesResponse>('/api/v1/users/roles/', {
    ...requestConfig,
    params: queryParams,
  })
  return response.data
}

