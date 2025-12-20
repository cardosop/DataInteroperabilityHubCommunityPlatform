/**
 * ProtectedRoute Component
 *
 * Comprehensive route protection component that handles:
 * - Authentication-based route guards
 * - Permission-based route guards
 * - Role-based route guards
 * - Loading states during authentication checks
 * - Unauthorized access handling
 * - Redirects with return URL preservation
 *
 * This component integrates all route protection logic in a single,
 * reusable component that works seamlessly with React Router.
 */

import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Box, CircularProgress, Typography } from '@mui/material'
import { useAuth } from '@/hooks/useAuth'
import {
  hasPermission,
  hasAnyPermission,
  hasAllPermissions,
  hasRole,
  hasAnyRole,
} from '@/lib/auth/auth'
import type { Permission, Role } from '@/lib/auth/types'

/**
 * ProtectedRoute props
 */
export interface ProtectedRouteProps {
  /**
   * Children to render if access is granted
   */
  children: React.ReactNode

  /**
   * Require authentication
   * @default false
   */
  requireAuth?: boolean

  /**
   * Required permission(s)
   */
  permissions?: Permission | Permission[]

  /**
   * Require all permissions (default: any)
   * @default false
   */
  requireAllPermissions?: boolean

  /**
   * Required role(s)
   */
  roles?: Role | Role[]

  /**
   * Redirect path when authentication fails
   * @default '/login'
   */
  redirectTo?: string

  /**
   * Redirect path when permission/role check fails
   * @default '/unauthorized'
   */
  unauthorizedRedirectTo?: string

  /**
   * Show loading state while checking authentication
   * @default true
   */
  showLoading?: boolean

  /**
   * Custom loading component
   */
  loadingComponent?: React.ReactNode

  /**
   * Custom unauthorized component (instead of redirect)
   */
  unauthorizedComponent?: React.ReactNode
}

/**
 * ProtectedRoute Component
 *
 * Protects routes based on authentication, permissions, and roles.
 * Handles loading states and unauthorized access scenarios.
 *
 * @example
 * ```tsx
 * // Require authentication
 * <ProtectedRoute requireAuth>
 *   <Dashboard />
 * </ProtectedRoute>
 *
 * // Require specific permission
 * <ProtectedRoute
 *   requireAuth
 *   permissions="assets.view"
 * >
 *   <AssetsPage />
 * </ProtectedRoute>
 *
 * // Require multiple permissions (any)
 * <ProtectedRoute
 *   requireAuth
 *   permissions={['assets.view', 'assets.edit']}
 * >
 *   <AssetsPage />
 * </ProtectedRoute>
 *
 * // Require all permissions
 * <ProtectedRoute
 *   requireAuth
 *   permissions={['assets.view', 'assets.edit']}
 *   requireAllPermissions
 * >
 *   <AssetsPage />
 * </ProtectedRoute>
 *
 * // Require specific role
 * <ProtectedRoute
 *   requireAuth
 *   roles="admin"
 * >
 *   <AdminPanel />
 * </ProtectedRoute>
 * ```
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requireAuth = false,
  permissions,
  requireAllPermissions = false,
  roles,
  redirectTo = '/login',
  unauthorizedRedirectTo = '/unauthorized',
  showLoading = true,
  loadingComponent,
  unauthorizedComponent,
}) => {
  const location = useLocation()
  const { user, isAuthenticated, isLoading, error } = useAuth()

  // Show loading state while checking authentication
  if (showLoading && isLoading) {
    if (loadingComponent) {
      return <>{loadingComponent}</>
    }

    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body2" color="text.secondary">
          Checking authentication...
        </Typography>
      </Box>
    )
  }

  // Check authentication requirement
  if (requireAuth) {
    if (!isAuthenticated) {
      // Save the attempted location for redirect after login
      return (
        <Navigate
          to={redirectTo}
          state={{ from: location, reason: 'authentication_required' }}
          replace
        />
      )
    }

    // If there's an authentication error, redirect to login
    if (error && !user) {
      return (
        <Navigate
          to={redirectTo}
          state={{ from: location, reason: 'authentication_error' }}
          replace
        />
      )
    }
  }

  // Check role requirement (only if authenticated)
  if (roles && isAuthenticated && user) {
    const roleArray = Array.isArray(roles) ? roles : [roles]
    const hasRequiredRole = hasAnyRole(user, roleArray)

    if (!hasRequiredRole) {
      if (unauthorizedComponent) {
        return <>{unauthorizedComponent}</>
      }

      return (
        <Navigate
          to={unauthorizedRedirectTo}
          state={{
            from: location,
            reason: 'role_required',
            requiredRoles: roleArray,
          }}
          replace
        />
      )
    }
  }

  // Check permission requirement (only if authenticated)
  if (permissions && isAuthenticated && user) {
    const permissionArray = Array.isArray(permissions)
      ? permissions
      : [permissions]

    const hasRequiredPermission = requireAllPermissions
      ? hasAllPermissions(user, permissionArray)
      : hasAnyPermission(user, permissionArray)

    if (!hasRequiredPermission) {
      if (unauthorizedComponent) {
        return <>{unauthorizedComponent}</>
      }

      return (
        <Navigate
          to={unauthorizedRedirectTo}
          state={{
            from: location,
            reason: 'permission_required',
            requiredPermissions: permissionArray,
            requireAll: requireAllPermissions,
          }}
          replace
        />
      )
    }
  }

  // All checks passed, render children
  return <>{children}</>
}

/**
 * Export ProtectedRoute as default
 */
export default ProtectedRoute

