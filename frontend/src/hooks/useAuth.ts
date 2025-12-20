/**
 * useAuth Hook
 *
 * Main authentication hook that provides:
 * - Authentication state (user, isAuthenticated, isLoading)
 * - Authentication methods (login, logout, register)
 * - Automatic token refresh
 * - User data synchronization
 *
 * This hook manages the complete authentication lifecycle and integrates
 * with React Query for state management and caching.
 */

import {
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  clearCurrentUser,
  getCurrentUser,
  refreshToken,
  type CurrentUserResponse,
  type LoginRequest,
  type LoginResponse,
  type RegisterRequest,
} from '@/lib/api/auth'
import { FetchError } from '@/lib/api/fetch'
import { queryKeys } from '@/lib/api/react-query'
import {
  clearAuthTokens,
  getAuthToken,
  getRefreshToken,
  getCurrentUser as getStoredUser,
  setCurrentUser,
  setAuthTokens as setTokens,
} from '@/lib/auth/auth'
import type { User } from '@/lib/auth/types'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'

/**
 * Authentication state
 */
export interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: Error | null
}

/**
 * Authentication methods
 */
export interface AuthMethods {
  login: (credentials: LoginRequest) => Promise<LoginResponse>
  logout: (invalidateAll?: boolean) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  refresh: () => Promise<void>
}

/**
 * useAuth hook return type
 */
export interface UseAuthReturn extends AuthState, AuthMethods {}

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
 * useAuth Hook
 *
 * Main authentication hook that manages authentication state and provides
 * methods for login, logout, and registration.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { user, isAuthenticated, login, logout } = useAuth()
 *
 *   if (!isAuthenticated) {
 *     return <LoginForm onLogin={login} />
 *   }
 *
 *   return (
 *     <div>
 *       <p>Welcome, {user?.name}</p>
 *       <button onClick={() => logout()}>Logout</button>
 *     </div>
 *   )
 * }
 * ```
 */
export function useAuth(): UseAuthReturn {
  const queryClient = useQueryClient()
  const [error, setError] = useState<Error | null>(null)
  // Track user updates to force re-renders when user is set during mutations
  const [userUpdateTrigger, setUserUpdateTrigger] = useState(0)

  // Check if we have a token
  const hasToken = getAuthToken() !== null
  // Get stored user - read it dynamically so it updates when setCurrentUser is called
  // This ensures the hook reflects the latest stored user even during mutations
  const storedUser = getStoredUser()

  // Also check query cache for user data (in case it was set directly)
  const cachedUserData = queryClient.getQueryData<CurrentUserResponse>(queryKeys.auth.user())

  // Query for current user (only if authenticated)
  // Check if we have query data set directly (e.g., from partial user scenario)
  // If so, don't enable the query to avoid overwriting it
  // Check dynamically so it updates when query data is set during mutations
  const currentQueryDataCheck = queryClient.getQueryData<CurrentUserResponse>(queryKeys.auth.user())
  const {
    data: userData,
    isLoading: isLoadingUser,
    error: userError,
    refetch: refetchUser,
  } = useQuery<CurrentUserResponse, Error>({
    queryKey: queryKeys.auth.user(),
    queryFn: async () => {
      const response = await getCurrentUser()
      const user = convertUserResponse(response)
      setCurrentUser(user)
      return response
    },
    // Only enable if we have a token AND don't already have query data
    // This prevents the query from fetching when we've set partial user data
    // Check dynamically on each render
    enabled: hasToken && !currentQueryDataCheck,
    retry: (failureCount, error) => {
      // Don't retry on 401 (unauthorized) or 500 (server errors)
      if (error instanceof FetchError) {
        const status = error.response?.status
        if (status === 401 || status === 500) {
        return false
        }
      }
      return failureCount < 2
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    // Use cached data if available to avoid unnecessary fetches
    initialData: cachedUserData,
    // Use placeholderData to ensure query data is available immediately if set during mutations
    placeholderData: currentQueryDataCheck || cachedUserData,
    // Ensure hook re-renders when query data changes, even if query is disabled
    notifyOnChangeProps: ['data', 'error', 'isLoading'],
  })

  // Convert user data to User type
  // Priority: userData from query > current query cache > storedUser > initial cached data
  // Check query cache dynamically (not just at initialization) to catch data set during mutations
  // Prioritize storedUser when available (set during login mutations) even if query is still loading
  const currentQueryData = queryClient.getQueryData<CurrentUserResponse>(queryKeys.auth.user())
  const user: User | null = userData
    ? convertUserResponse(userData)
    : storedUser // Prioritize storedUser - it's set immediately during mutations
      ? storedUser
      : currentQueryData
        ? convertUserResponse(currentQueryData)
        : cachedUserData
          ? convertUserResponse(cachedUserData)
          : null

  // Determine authentication state
  const isAuthenticated = hasToken && !!user && !isLoadingUser

  // Login mutation
  const loginMutation = useMutation<LoginResponse, Error, LoginRequest>({
    mutationFn: async credentials => {
      const response = await apiLogin(credentials)

      // Store tokens
      setTokens(response.access_token, response.refresh_token, response.expires_in)

      // Store tenant ID if available
      if (response.user?.tenant_id) {
        localStorage.setItem('auth_tenant_id', response.user.tenant_id)
      }

      // Fetch full user data
      let userFetchSucceeded = false
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
        userFetchSucceeded = true
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
          // Set query data directly to avoid triggering another fetch
          const partialUserResponse: CurrentUserResponse = {
            id: response.user.id,
            email: response.user.email,
            name: response.user.name,
            tenant_id: response.user.tenant_id,
            roles: [],
            permissions: [],
          }
          // Cancel any in-flight queries to prevent them from overwriting our data
          queryClient.cancelQueries({ queryKey: queryKeys.auth.user() })
          // Set query data directly - this will trigger a re-render with the user data
          queryClient.setQueryData(queryKeys.auth.user(), partialUserResponse)
          // Force hook to re-render by updating state
          // This ensures the hook sees the new storedUser and query data
          setUserUpdateTrigger(prev => prev + 1)
          // Also ensure storedUser is set (it's already set above, but this ensures consistency)
          // The hook will re-render because state changed, and storedUser will be read fresh
        }
      }

      // Only invalidate and refetch user query if /me succeeded
      // If /me failed, we're using partial user data and don't want to trigger another failed query
      if (userFetchSucceeded) {
      await queryClient.invalidateQueries({ queryKey: queryKeys.auth.user() })
        // Reset query to clear any previous errors
        await queryClient.resetQueries({ queryKey: queryKeys.auth.user() })
      }
      // If /me failed, we already set the query data above, so no need to reset/invalidate

      return response
    },
    onError: err => {
      setError(err)
      clearAuthTokens()
      clearCurrentUser()
    },
    onSuccess: () => {
      setError(null)
      // Clear any user query errors by resetting the query
      queryClient.resetQueries({ queryKey: queryKeys.auth.user() })
    },
  })

  // Logout mutation
  const logoutMutation = useMutation<void, Error, boolean | undefined>({
    mutationFn: async (invalidateAll = false) => {
      const refreshTokenValue = getRefreshToken()
      const accessToken = getAuthToken()

      // Clear local storage first (optimistic logout)
      clearAuthTokens()

      // Try to invalidate tokens on server (non-blocking)
      if (refreshTokenValue || invalidateAll) {
        try {
          await apiLogout(
            invalidateAll,
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
          console.warn('[Auth] Failed to invalidate tokens on server:', err)
        }
      }

      // Clear all queries
      queryClient.clear()
    },
    onError: err => {
      setError(err)
      // Still clear local state even if server logout fails
      clearAuthTokens()
      clearCurrentUser()
    },
    onSuccess: () => {
      setError(null)
      // Clear any user query errors by resetting the query
      queryClient.resetQueries({ queryKey: queryKeys.auth.user() })
    },
  })

  // Register mutation
  const registerMutation = useMutation<void, Error, RegisterRequest>({
    mutationFn: async data => {
      await apiRegister(data)
      // Registration doesn't automatically log in, user needs to login separately
    },
    onError: err => {
      setError(err)
    },
    onSuccess: () => {
      setError(null)
    },
  })

  // Refresh token function
  const refresh = useCallback(async () => {
    const refreshTokenValue = getRefreshToken()
    if (!refreshTokenValue) {
      throw new Error('No refresh token available')
    }

    try {
      const response = await refreshToken({
        refresh_token: refreshTokenValue,
      })

      // Update stored tokens
      setTokens(
        response.access_token,
        response.refresh_token || refreshTokenValue,
        response.expires_in
      )

      // Refetch user data (non-blocking - if it fails, tokens are still valid)
      try {
      await refetchUser()
      } catch (userErr) {
        // User fetch failed, but tokens are still valid
        // Log warning but don't clear tokens
        console.warn('[Auth] Failed to refetch user after token refresh:', userErr)
      }
    } catch (err) {
      // Refresh token API call failed, clear auth
      clearAuthTokens()
      clearCurrentUser()
      throw err
    }
  }, [refetchUser])

  // Auto-refresh token when it's about to expire
  useEffect(() => {
    if (!hasToken || !user) return

    const token = getAuthToken()
    if (!token) return

    // Check token expiration (simplified - in production, decode JWT to get exact expiry)
    const checkInterval = setInterval(
      async () => {
        try {
          // Try to refresh token proactively
          await refresh()
        } catch (err) {
          // Refresh failed, user will need to login again
          console.warn('[Auth] Token refresh failed:', err)
        }
      },
      5 * 60 * 1000
    ) // Check every 5 minutes

    return () => clearInterval(checkInterval)
  }, [hasToken, user, refresh])

  return {
    user,
    isAuthenticated,
    isLoading: isLoadingUser,
    error: error || (userError as Error) || null,
    login: loginMutation.mutateAsync,
    logout: logoutMutation.mutateAsync,
    register: registerMutation.mutateAsync,
    refresh,
  }
}
