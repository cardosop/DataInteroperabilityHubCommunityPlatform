/**
 * AuthGuard Component
 *
 * Route guard for protecting routes that require authentication.
 * Uses the useAuth hook for proper authentication state management.
 */

import React from 'react'
import { ProtectedRoute } from '../ProtectedRoute'

export interface AuthGuardProps {
  children: React.ReactNode
  /**
   * Redirect path when not authenticated
   * @default '/login'
   */
  redirectTo?: string
  /**
   * Show loading state while checking authentication
   * @default true
   */
  loading?: boolean
}

/**
 * AuthGuard - Protects routes that require authentication
 *
 * This is a convenience wrapper around ProtectedRoute for authentication-only checks.
 * For more complex scenarios (permissions, roles), use ProtectedRoute directly.
 *
 * @example
 * ```tsx
 * <AuthGuard redirectTo="/login">
 *   <Dashboard />
 * </AuthGuard>
 * ```
 */
export const AuthGuard: React.FC<AuthGuardProps> = ({
  children,
  redirectTo = '/login',
  loading = true,
}) => {
  return (
    <ProtectedRoute
      requireAuth
      redirectTo={redirectTo}
      showLoading={loading}
    >
      {children}
    </ProtectedRoute>
  )
}

