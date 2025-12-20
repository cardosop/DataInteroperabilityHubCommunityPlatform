/**
 * PermissionGuard Component
 *
 * Route guard for protecting routes that require specific permissions.
 * Uses the useAuth hook for proper authentication state management.
 */

import React from 'react'
import { Box, Typography } from '@mui/material'
import { ProtectedRoute } from '../ProtectedRoute'
import type { Permission } from '@/lib/auth/types'

export interface PermissionGuardProps {
  children: React.ReactNode
  /**
   * Required permission(s)
   */
  permission?: Permission | Permission[]
  /**
   * Require all permissions (default: any)
   */
  requireAll?: boolean
  /**
   * Redirect path when permission check fails
   * @default '/unauthorized'
   */
  redirectTo?: string
  /**
   * Show custom unauthorized message instead of redirecting
   */
  showMessage?: boolean
}

/**
 * PermissionGuard - Protects routes that require specific permissions
 *
 * This is a convenience wrapper around ProtectedRoute for permission checks.
 * It automatically requires authentication before checking permissions.
 *
 * @example
 * ```tsx
 * <PermissionGuard permission="assets.view">
 *   <AssetsPage />
 * </PermissionGuard>
 *
 * <PermissionGuard
 *   permission={['assets.view', 'assets.edit']}
 *   requireAll
 * >
 *   <AssetsPage />
 * </PermissionGuard>
 * ```
 */
export const PermissionGuard: React.FC<PermissionGuardProps> = ({
  children,
  permission,
  requireAll = false,
  redirectTo = '/unauthorized',
  showMessage = false,
}) => {
  if (!permission) {
    // No permission required, allow access
    return <>{children}</>
  }

  const unauthorizedComponent = showMessage ? (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        padding: 4,
      }}
    >
      <Typography variant="h4" gutterBottom>
        Access Denied
      </Typography>
      <Typography variant="body1" color="text.secondary">
        You don't have permission to access this page.
      </Typography>
    </Box>
  ) : undefined

  return (
    <ProtectedRoute
      requireAuth
      permissions={permission}
      requireAllPermissions={requireAll}
      unauthorizedRedirectTo={redirectTo}
      unauthorizedComponent={unauthorizedComponent}
    >
      {children}
    </ProtectedRoute>
  )
}

