/**
 * useLogout Hook
 *
 * Mutation hook for user logout.
 * Provides logout functionality with automatic token invalidation.
 *
 * @example
 * ```tsx
 * function LogoutButton() {
 *   const logout = useLogout()
 *
 *   const handleLogout = async () => {
 *     try {
 *       await logout.mutateAsync()
 *       // Redirect to login page
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <button onClick={handleLogout} disabled={logout.isPending}>
 *       Logout
 *     </button>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  logout as apiLogout,
  type LogoutRequest,
} from '@/lib/api/auth'
import {
  getAuthToken,
  getRefreshToken,
  clearAuthTokens,
} from '@/lib/auth/auth'

/**
 * Logout options
 */
export interface LogoutOptions {
  /**
   * If true, invalidates all refresh tokens for the user
   * @default false
   */
  invalidateAll?: boolean
}

/**
 * useLogout Hook
 *
 * Mutation hook for user logout.
 *
 * @returns Logout mutation object with mutate, mutateAsync, and state
 */
export function useLogout() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, LogoutOptions | undefined>({
    mutationFn: async (options) => {
      const { invalidateAll = false } = options || {}
      const refreshTokenValue = getRefreshToken()
      const accessToken = getAuthToken()

      // Clear local storage first (optimistic logout)
      clearAuthTokens()
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_tenant_id')
      }

      // Try to invalidate tokens on server (non-blocking)
      if (refreshTokenValue || invalidateAll) {
        try {
          const logoutData: LogoutRequest = invalidateAll
            ? {}
            : { refresh_token: refreshTokenValue }

          await apiLogout(
            logoutData,
            accessToken
              ? {
                  headers: {
                    Authorization: `Bearer ${accessToken}`,
                  },
                }
              : undefined
          )
        } catch (err) {
          // Log error but don't throw - logout should always succeed locally
          console.warn('[Logout] Failed to invalidate tokens on server:', err)
        }
      }

      // Clear all queries
      queryClient.clear()
    },
    onError: (error) => {
      // Error handling - still clear local state even if server logout fails
      console.error('[Logout] Logout error:', error)
      clearAuthTokens()
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_tenant_id')
      }
    },
    onSuccess: () => {
      // Success - local state already cleared
    },
  })
}

