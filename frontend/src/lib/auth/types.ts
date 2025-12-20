/**
 * Authentication Types
 *
 * Type definitions for authentication and authorization.
 */

export interface User {
  id: string
  email: string
  name?: string
  roles: string[]
  permissions: string[]
  tenantId?: string
}

export interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
}

export type Permission = string
export type Role = string

