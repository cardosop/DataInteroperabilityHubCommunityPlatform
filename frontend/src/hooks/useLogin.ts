/**
 * useLogin Hook
 *
 * Mutation hook for user login.
 * Provides login functionality with loading states and error handling.
 *
 * @example
 * ```tsx
 * function LoginForm() {
 *   const login = useLogin()
 *
 *   const handleSubmit = async (e: FormEvent) => {
 *     e.preventDefault()
 *     try {
 *       await login.mutateAsync({
 *         email: 'user@example.com',
 *         password: 'password123'
 *       })
 *       // Redirect to dashboard
 *     } catch (error) {
 *       // Handle error
 *     }
 *   }
 *
 *   return (
 *     <form onSubmit={handleSubmit}>
 *       <!-- form fields -->
 *       <button disabled={login.isPending}>Login</button>
 *     </form>
 *   )
 * }
 * ```
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  login as apiLogin,
  getCurrentUser,
  type LoginRequest,
  type LoginResponse,
  type CurrentUserResponse,
} from '@/lib/api/auth'
import {
  setAuthTokens,
  setCurrentUser,
  getRefreshToken,
} from '@/lib/auth/auth'
import { queryKeys } from '@/lib/api/react-query'
import type { User } from '@/lib/auth/types'

/**
 * Convert API user response to User type
 */
function convertUserResponse(response: CurrentUserResponse): User {
  return {
    id: response.id,
    email: response.email,
    name: response.name || undefined,
    roles: response.roles || [],
    permissions: response.permissions || [],
    tenantId: response.tenant_id || undefined,
  }
}

/**
 * useLogin Hook
 *
 * Mutation hook for user login.
 *
 * @returns Login mutation object with mutate, mutateAsync, and state
 */
export function useLogin() {
  const queryClient = useQueryClient()

  return useMutation<LoginResponse, Error, LoginRequest>({
    mutationFn: async (credentials) => {
      const response = await apiLogin(credentials)

      // Store tokens
      setAuthTokens(
        response.access_token,
        response.refresh_token,
        response.expires_in
      )

      // Store tenant ID if available
      if (response.user?.tenant_id) {
        localStorage.setItem('auth_tenant_id', response.user.tenant_id)
      }

      // Fetch full user data
      try {
        const userResponse = await getCurrentUser({
          headers: {
            Authorization: `Bearer ${response.access_token}`,
          },
        } as any)
        const fullUser = convertUserResponse(userResponse)
        setCurrentUser(fullUser)

        // Update tenant ID from user data
        if (fullUser.tenantId) {
          localStorage.setItem('auth_tenant_id', fullUser.tenantId)
        }
      } catch (err) {
        // If /me fails, use partial user data from login response
        if (response.user) {
          const partialUser: User = {
            id: response.user.id,
            email: response.user.email,
            name: response.user.name,
            roles: [],
            permissions: [],
            tenantId: response.user.tenant_id,
          }
          setCurrentUser(partialUser)
        }
      }

      // Invalidate and refetch user query
      await queryClient.invalidateQueries({ queryKey: queryKeys.auth.user() })

      return response
    },
    onError: (error) => {
      // Error handling is done by the caller
      console.error('[Login] Login failed:', error)
    },
    onSuccess: () => {
      // Success handling can be done by the caller
    },
  })
}

