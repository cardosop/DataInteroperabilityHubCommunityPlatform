/**
 * Authentication Utilities
 *
 * Utilities for authentication and authorization checks.
 */

import type { User, Permission, Role } from './types'

/**
 * Storage keys for authentication data
 * Must match @/lib/api/auth.ts STORAGE_KEYS for consistency
 */
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'auth_access_token',
  REFRESH_TOKEN: 'auth_refresh_token',
  TOKEN_EXPIRES_AT: 'auth_token_expires_at',
  TENANT_ID: 'auth_tenant_id',
  USER: 'auth_user',
} as const

/**
 * Get authentication token from storage
 * Uses auth_access_token to match API auth service
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
}

/**
 * Set authentication token in storage
 */
export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, token)
}

/**
 * Remove authentication token from storage
 */
export function removeAuthToken(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return getAuthToken() !== null
}

/**
 * Get current user from storage (if available)
 */
export function getCurrentUser(): User | null {
  if (typeof window === 'undefined') return null
  const userStr = localStorage.getItem(STORAGE_KEYS.USER)
  if (!userStr) return null
  try {
    return JSON.parse(userStr) as User
  } catch {
    return null
  }
}

/**
 * Set current user in storage
 */
export function setCurrentUser(user: User): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user))
}

/**
 * Remove current user from storage
 */
export function removeCurrentUser(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEYS.USER)
}

/**
 * Check if user has a specific permission
 */
export function hasPermission(user: User | null, permission: Permission): boolean {
  if (!user) return false
  return user.permissions.includes(permission) || user.permissions.includes('*')
}

/**
 * Check if user has any of the specified permissions
 */
export function hasAnyPermission(
  user: User | null,
  permissions: Permission[]
): boolean {
  if (!user) return false
  return permissions.some((permission) => hasPermission(user, permission))
}

/**
 * Check if user has all of the specified permissions
 */
export function hasAllPermissions(
  user: User | null,
  permissions: Permission[]
): boolean {
  if (!user) return false
  return permissions.every((permission) => hasPermission(user, permission))
}

/**
 * Check if user has a specific role
 */
export function hasRole(user: User | null, role: Role): boolean {
  if (!user) return false
  return user.roles.includes(role) || user.roles.includes('admin')
}

/**
 * Check if user has any of the specified roles
 */
export function hasAnyRole(user: User | null, roles: Role[]): boolean {
  if (!user) return false
  return roles.some((role) => hasRole(user, role))
}

/**
 * Get refresh token from storage
 */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
}

/**
 * Set refresh token in storage
 */
export function setRefreshToken(token: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, token)
}

/**
 * Remove refresh token from storage
 */
export function removeRefreshToken(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
}

/**
 * Set authentication tokens (access and refresh)
 */
export function setAuthTokens(
  accessToken: string,
  refreshToken: string,
  expiresIn: number
): void {
  if (typeof window === 'undefined') return
  setAuthToken(accessToken)
  setRefreshToken(refreshToken)
  // Store expiration time
  const expiresAt = Date.now() + expiresIn * 1000
  localStorage.setItem(STORAGE_KEYS.TOKEN_EXPIRES_AT, expiresAt.toString())
}

/**
 * Clear all authentication data
 */
export function clearAuth(): void {
  removeAuthToken()
  removeRefreshToken()
  removeCurrentUser()
  if (typeof window !== 'undefined') {
    localStorage.removeItem(STORAGE_KEYS.TOKEN_EXPIRES_AT)
    localStorage.removeItem(STORAGE_KEYS.TENANT_ID)
  }
}

/**
 * Clear all authentication tokens (alias for clearAuth for consistency)
 */
export function clearAuthTokens(): void {
  clearAuth()
}

