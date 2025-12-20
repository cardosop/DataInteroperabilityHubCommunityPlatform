/**
 * RoleGuard Component
 *
 * Route guard for protecting routes that require specific roles.
 * Uses the useAuth hook for proper authentication state management.
 */

import React from 'react'
import { Box, Typography } from '@mui/material'
import { ProtectedRoute } from '../ProtectedRoute'
import type { Role } from '@/lib/auth/types'

export interface RoleGuardProps {
  children: React.ReactNode
  /**
   * Required role(s)
   */
  role?: Role | Role[]
  /**
   * Redirect path when role check fails
   * @default '/unauthorized'
   */
  redirectTo?: string
  /**
   * Show custom unauthorized message instead of redirecting
   */
  showMessage?: boolean
}

/**
 * RoleGuard - Protects routes that require specific roles
 *
 * This is a convenience wrapper around ProtectedRoute for role checks.
 * It automatically requires authentication before checking roles.
 *
 * @example
 * ```tsx
 * <RoleGuard role="admin">
 *   <AdminPanel />
 * </RoleGuard>
 *
 * <RoleGuard role={['admin', 'moderator']}>
 *   <ModeratorPanel />
 * </RoleGuard>
 * ```
 */
export const RoleGuard: React.FC<RoleGuardProps> = ({
  children,
  role,
  redirectTo = '/unauthorized',
  showMessage = false,
}) => {
  if (!role) {
    // No role required, allow access
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
        You don't have the required role to access this page.
      </Typography>
    </Box>
  ) : undefined

  return (
    <ProtectedRoute
      requireAuth
      roles={role}
      unauthorizedRedirectTo={redirectTo}
      unauthorizedComponent={unauthorizedComponent}
    >
      {children}
    </ProtectedRoute>
  )
}

