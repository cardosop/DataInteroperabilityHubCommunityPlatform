/**
 * Route Types
 *
 * Type definitions for routing configuration.
 */

import { ReactNode } from 'react'
import type { Permission, Role } from '@/lib/auth/types'

export interface RouteConfig {
  /**
   * Route path
   */
  path: string
  /**
   * Route element (lazy-loaded component)
   */
  element: ReactNode
  /**
   * Route label for navigation
   */
  label?: string
  /**
   * Route icon (for navigation)
   */
  icon?: ReactNode
  /**
   * Require authentication
   */
  requireAuth?: boolean
  /**
   * Required permissions
   */
  permissions?: Permission | Permission[]
  /**
   * Require all permissions (default: any)
   */
  requireAllPermissions?: boolean
  /**
   * Required roles
   */
  roles?: Role | Role[]
  /**
   * Redirect path when guard fails
   */
  redirectTo?: string
  /**
   * Nested routes
   */
  children?: RouteConfig[]
  /**
   * Route metadata
   */
  meta?: {
    title?: string
    description?: string
    [key: string]: unknown
  }
}

