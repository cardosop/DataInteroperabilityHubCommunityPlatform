/**
 * Authentication Service
 *
 * Comprehensive authentication service for managing tokens, login, logout,
 * and automatic token refresh. This service handles:
 * - Access and refresh token management
 * - Automatic token refresh with retry logic
 * - Login and logout operations
 * - Tenant ID management
 * - Token expiration handling
 * - API functions for authentication operations
 *
 * This service integrates with the API client to automatically handle
 * authentication headers and token refresh on 401 errors.
 */

import type { User } from '../auth/types'
import { config } from '../config'
import { apiClient, createPublicApiClient } from './client'
import { ApiError, NetworkError, parseApiError } from './errors'
import { FetchError } from './fetch'
import type { ExtendedFetchRequestInit } from './types'

/**
 * Storage keys for authentication data
 */
const STORAGE_KEYS = {
  ACCESS_TOKEN: 'auth_access_token',
  REFRESH_TOKEN: 'auth_refresh_token',
  TOKEN_EXPIRES_AT: 'auth_token_expires_at',
  TENANT_ID: 'auth_tenant_id',
  USER: 'auth_user',
} as const

/**
 * Login request payload
 */
export interface LoginRequest {
  email: string
  password: string
  remember_me?: boolean
}

/**
 * Login response from API
 */
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user?: {
    id: string
    email: string
    name?: string
    tenant_id?: string
    roles?: string[]
    permissions?: string[]
  }
}

/**
 * Register request payload
 */
export interface RegisterRequest {
  email: string
  password: string
  name: string
  tenant_id?: string
}

/**
 * Register response
 */
export interface RegisterResponse {
  id: string
  email: string
  name: string
  tenant_id?: string | null
  created_at: string
}

/**
 * Password reset request payload
 */
export interface PasswordResetRequest {
  email: string
}

/**
 * Password reset request response
 */
export interface PasswordResetRequestResponse {
  message: string
}

/**
 * Password reset confirm payload
 */
export interface PasswordResetConfirmRequest {
  token: string
  new_password: string
}

/**
 * Password reset confirm response
 */
export interface PasswordResetConfirmResponse {
  message: string
}

/**
 * Token refresh request
 */
export interface RefreshTokenRequest {
  refresh_token: string
}

/**
 * Token refresh response
 */
export interface RefreshTokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
}

/**
 * Authentication state
 */
export interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  expiresAt: number | null
  tenantId: string | null
  user: User | null
  isAuthenticated: boolean
}

/**
 * Token refresh options
 */
interface RefreshOptions {
  /**
   * Whether to force refresh even if token is not expired
   */
  force?: boolean
  /**
   * Maximum number of retry attempts
   */
  maxRetries?: number
}

/**
 * Authentication error class
 */
export class AuthenticationError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly status?: number
  ) {
    super(message)
    this.name = 'AuthenticationError'
  }
}

/**
 * Logout request
 */
export interface LogoutRequest {
  refresh_token?: string
}

/**
 * Logout response
 */
export interface LogoutResponse {
  message: string
  revoked_sessions: number
}

/**
 * API Key
 */
export interface APIKey {
  id: string
  name: string
  scopes: string[]
  expires_at: string | null
  last_used_at: string | null
  created_at: string
}

/**
 * Create API Key request
 */
export interface CreateAPIKeyRequest {
  name: string
  scopes?: string[]
  expires_in_days?: number | null
}

/**
 * Create API Key response (includes plaintext key shown only once)
 */
export interface CreateAPIKeyResponse {
  id: string
  name: string
  api_key: string
  scopes: string[]
  expires_at: string | null
  created_at: string
}

/**
 * List API Keys response
 */
export interface ListAPIKeysResponse {
  count: number
  next: string | null
  previous: string | null
  results: APIKey[]
}

/**
 * Current user response
 */
export interface CurrentUserResponse {
  id: string
  email: string
  name: string | null
  tenant_id: string | null
  roles: string[]
  permissions: string[]
  created_at: string
  last_login_at: string | null
}

/**
 * Get access token from storage
 *
 * @returns Access token or null if not found
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN)
}

/**
 * Get refresh token from storage
 *
 * @returns Refresh token or null if not found
 */
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
}

/**
 * Get token expiration timestamp
 *
 * @returns Expiration timestamp in milliseconds or null
 */
export function getTokenExpiresAt(): number | null {
  if (typeof window === 'undefined') return null
  const expiresAt = localStorage.getItem(STORAGE_KEYS.TOKEN_EXPIRES_AT)
  return expiresAt ? parseInt(expiresAt, 10) : null
}

/**
 * Check if access token is expired or will expire soon
 *
 * @param bufferSeconds - Buffer time in seconds before expiration to consider token expired (default: 60)
 * @returns True if token is expired or will expire soon
 */
export function isTokenExpired(bufferSeconds: number = 60): boolean {
  const expiresAt = getTokenExpiresAt()
  if (!expiresAt) return true

  const now = Date.now()
  const bufferMs = bufferSeconds * 1000
  return now >= expiresAt - bufferMs
}

/**
 * Set authentication tokens in storage
 *
 * @param accessToken - Access token
 * @param refreshToken - Refresh token
 * @param expiresIn - Token expiration time in seconds
 */
export function setAuthTokens(accessToken: string, refreshToken: string, expiresIn: number): void {
  if (typeof window === 'undefined') return

  const expiresAt = Date.now() + expiresIn * 1000

  localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, accessToken)
  localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken)
  localStorage.setItem(STORAGE_KEYS.TOKEN_EXPIRES_AT, expiresAt.toString())
}

/**
 * Clear all authentication tokens from storage
 */
export function clearAuthTokens(): void {
  if (typeof window === 'undefined') return

  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.TOKEN_EXPIRES_AT)
  localStorage.removeItem(STORAGE_KEYS.TENANT_ID)
  localStorage.removeItem(STORAGE_KEYS.USER)
}

/**
 * Get tenant ID from storage
 *
 * @returns Tenant ID or null if not found
 */
export function getTenantId(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(STORAGE_KEYS.TENANT_ID)
}

/**
 * Set tenant ID in storage
 *
 * @param tenantId - Tenant ID
 */
export function setTenantId(tenantId: string): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEYS.TENANT_ID, tenantId)
}

/**
 * Clear tenant ID from storage
 */
export function clearTenantId(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEYS.TENANT_ID)
}

/**
 * Get current user from storage
 *
 * @returns User object or null if not found
 */
export function getStoredUser(): User | null {
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
 *
 * @param user - User object
 */
export function setCurrentUser(user: User): void {
  if (typeof window === 'undefined') return
  localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user))
}

/**
 * Clear current user from storage
 */
export function clearCurrentUser(): void {
  if (typeof window === 'undefined') return
  localStorage.removeItem(STORAGE_KEYS.USER)
}

/**
 * Get complete authentication state
 *
 * @returns Current authentication state
 */
export function getAuthState(): AuthState {
  const accessToken = getAuthToken()
  const refreshToken = getRefreshToken()
  const expiresAt = getTokenExpiresAt()
  const tenantId = getTenantId()
  const user = getStoredUser()

  return {
    accessToken,
    refreshToken,
    expiresAt,
    tenantId,
    user,
    isAuthenticated: !!accessToken && !isTokenExpired(),
  }
}

/**
 * Refresh access token using refresh token
 *
 * This function:
 * - Retrieves the refresh token from storage
 * - Calls the refresh endpoint
 * - Updates stored tokens
 * - Returns the new access token
 *
 * @param options - Refresh options
 * @returns New access token or null if refresh failed
 * @throws AuthenticationError if refresh fails
 */
export async function refreshAuthToken(options: RefreshOptions = {}): Promise<string | null> {
  const { force = false, maxRetries = 3 } = options

  // Check if token refresh is needed
  if (!force && !isTokenExpired()) {
    const token = getAuthToken()
    if (token) return token
  }

  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    throw new AuthenticationError('No refresh token available', 'NO_REFRESH_TOKEN')
  }

  // Create a public API client (no auth required for refresh endpoint)
  const publicClient = createPublicApiClient()

  let lastError: Error | null = null

  // Retry logic for token refresh
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await publicClient.post<RefreshTokenResponse>(
        '/api/v1/auth/refresh/',
        {
          refresh_token: refreshToken,
        } as RefreshTokenRequest,
        {
          skipAuth: true,
          skipTenantId: true,
        } as ExtendedFetchRequestInit
      )

      const { access_token, expires_in } = response.data

      // Update stored tokens
      setAuthTokens(access_token, refreshToken, expires_in)

      return access_token
    } catch (error) {
      lastError = error as FetchError | Error

      // Parse error to get more details
      const apiError = parseApiError(lastError)

      // If it's a 401 or 400, the refresh token is invalid - clear auth
      if (apiError instanceof ApiError && (apiError.status === 401 || apiError.status === 400)) {
        clearAuthTokens()
        clearTenantId()

        throw new AuthenticationError(
          apiError.message || 'Refresh token is invalid or expired',
          'INVALID_REFRESH_TOKEN',
          apiError.status
        )
      }

      // For network errors or other errors, retry if attempts remain
      if (attempt < maxRetries - 1) {
        // Exponential backoff: 1s, 2s, 4s
        const delay = Math.pow(2, attempt) * 1000
        await new Promise(resolve => setTimeout(resolve, delay))
        continue
      }
    }
  }

  // All retries failed
  if (lastError) {
    const apiError = parseApiError(lastError)
    throw new AuthenticationError(
      apiError instanceof NetworkError
        ? 'Network error during token refresh'
        : apiError.message || 'Failed to refresh token',
      'REFRESH_FAILED',
      apiError instanceof ApiError ? apiError.status : undefined
    )
  }

  throw new AuthenticationError('Failed to refresh token', 'REFRESH_FAILED')
}

/**
 * Check if user is authenticated
 *
 * @returns True if user has valid access token
 */
export function isAuthenticated(): boolean {
  const token = getAuthToken()
  if (!token) return false
  return !isTokenExpired()
}

/**
 * Get access token, refreshing if necessary
 *
 * This is the main function to use when you need an access token.
 * It automatically handles token refresh if the token is expired.
 *
 * @param options - Refresh options
 * @returns Access token or null if not authenticated
 * @throws AuthenticationError if token refresh fails
 */
export async function getValidAuthToken(options: RefreshOptions = {}): Promise<string | null> {
  // If not authenticated, return null
  if (!isAuthenticated()) {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      // Try to refresh
      try {
        return await refreshAuthToken({ ...options, force: true })
      } catch {
        // Refresh failed, user needs to login again
        return null
      }
    }
    return null
  }

  // Token is valid, return it
  return getAuthToken()
}

/**
 * Login user with email and password
 *
 * This function:
 * - Calls the login endpoint
 * - Stores tokens and user data
 * - Fetches full user info from /me endpoint
 * - Manages tenant ID
 *
 * @param credentials - Login credentials
 * @param requestConfig - Optional Axios request config
 * @returns Login response with tokens and user info
 * @throws AuthenticationError if login fails
 */
export async function login(
  credentials: LoginRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<LoginResponse> {
  const publicClient = createPublicApiClient()

  try {
    const response = await publicClient.post<LoginResponse>('/api/v1/auth/login/', credentials, {
      ...requestConfig,
      skipAuth: true,
      skipTenantId: true,
    } as ExtendedFetchRequestInit)

    const { access_token, refresh_token, expires_in, user } = response.data

    // Store tokens
    setAuthTokens(access_token, refresh_token, expires_in)

    // Store tenant ID if available
    if (user?.tenant_id) {
      setTenantId(user.tenant_id)
    }

    // Fetch and store full user info from /me endpoint
    try {
      const userResponse = await publicClient.get<CurrentUserResponse>('/api/v1/auth/me/', {
        headers: {
          Authorization: `Bearer ${access_token}`,
        },
      } as ExtendedFetchRequestInit)

      const fullUser: User = {
        id: userResponse.data.id,
        email: userResponse.data.email,
        name: userResponse.data.name || undefined,
        roles: userResponse.data.roles || [],
        permissions: userResponse.data.permissions || [],
        tenantId: userResponse.data.tenant_id || undefined,
      }

      setCurrentUser(fullUser)

      // Update tenant ID from user data if not already set
      if (fullUser.tenantId && !getTenantId()) {
        setTenantId(fullUser.tenantId)
      }
    } catch (userError) {
      // If /me fails, use the user data from login response
      if (user) {
        const partialUser: User = {
          id: user.id,
          email: user.email,
          name: user.name,
          roles: user.roles || [],
          permissions: user.permissions || [],
          tenantId: user.tenant_id,
        }
        setCurrentUser(partialUser)
      }
    }

    return response.data
  } catch (error) {
    const apiError = parseApiError(error as FetchError | Error)

    if (apiError instanceof ApiError) {
      throw new AuthenticationError(
        apiError.message || 'Invalid email or password',
        apiError.code || 'LOGIN_FAILED',
        apiError.status
      )
    }

    if (apiError instanceof NetworkError) {
      throw new AuthenticationError(
        'Network error. Please check your connection and try again.',
        'NETWORK_ERROR'
      )
    }

    throw new AuthenticationError('An unexpected error occurred during login', 'LOGIN_FAILED')
  }
}

/**
 * Register new user
 *
 * @param data - Registration data
 * @param config - Optional Axios request config
 * @returns Registration response
 */
export async function register(
  data: RegisterRequest,
  config?: ExtendedFetchRequestInit
): Promise<RegisterResponse> {
  const response = await apiClient.post<RegisterResponse>('/api/v1/auth/register/', data, {
    ...config,
    skipAuth: true, // Registration endpoint doesn't require auth
    skipTenantId: true, // Registration endpoint doesn't require tenant ID
  } as ExtendedFetchRequestInit)
  return response.data
}

/**
 * Request password reset
 *
 * @param data - Password reset request data
 * @param config - Optional Axios request config
 * @returns Password reset request response
 */
export async function requestPasswordReset(
  data: PasswordResetRequest,
  config?: ExtendedFetchRequestInit
): Promise<PasswordResetRequestResponse> {
  const response = await apiClient.post<PasswordResetRequestResponse>(
    '/api/v1/auth/password-reset/',
    data,
    {
      ...config,
      skipAuth: true, // Password reset endpoint doesn't require auth
      skipTenantId: true, // Password reset endpoint doesn't require tenant ID
    } as ExtendedFetchRequestInit
  )
  return response.data
}

/**
 * Confirm password reset
 *
 * @param data - Password reset confirmation data
 * @param config - Optional Axios request config
 * @returns Password reset confirmation response
 */
export async function confirmPasswordReset(
  data: PasswordResetConfirmRequest,
  config?: ExtendedFetchRequestInit
): Promise<PasswordResetConfirmResponse> {
  const response = await apiClient.post<PasswordResetConfirmResponse>(
    '/api/v1/auth/password-reset/confirm/',
    data,
    {
      ...config,
      skipAuth: true, // Password reset confirmation endpoint doesn't require auth
      skipTenantId: true, // Password reset confirmation endpoint doesn't require tenant ID
    } as ExtendedFetchRequestInit
  )
  return response.data
}

/**
 * Refresh access token (API function - use refreshAuthToken for automatic token management)
 *
 * @param data - Refresh token data
 * @param requestConfig - Optional Axios request config
 * @returns Token refresh response
 */
export async function refreshToken(
  data: RefreshTokenRequest,
  requestConfig?: ExtendedFetchRequestInit
): Promise<RefreshTokenResponse> {
  // Use public client for refresh endpoint (no auth required)
  const publicClient = createPublicApiClient()
  const response = await publicClient.post<RefreshTokenResponse>('/api/v1/auth/refresh/', data, {
    ...requestConfig,
    skipAuth: true, // Token refresh uses refresh token, not access token
    skipTenantId: true, // Token refresh doesn't require tenant ID
  } as ExtendedFetchRequestInit)
  return response.data
}

/**
 * Logout user and invalidate tokens
 *
 * This function:
 * - Calls the logout endpoint to invalidate refresh tokens on the server
 * - Clears all authentication data from storage
 *
 * @param invalidateAll - If true, invalidates all refresh tokens for the user (default: false)
 * @param requestConfig - Optional Axios request config
 * @throws AuthenticationError if logout fails (non-critical, auth is still cleared locally)
 */
export async function logout(
  invalidateAll: boolean = false,
  requestConfig?: ExtendedFetchRequestInit
): Promise<void> {
  const refreshToken = getRefreshToken()
  // Get access token from storage first, but also check request config headers
  // in case tokens were already cleared (e.g., by useAuth hook)
  let accessToken = getAuthToken()

  // If access token is not in storage, try to extract it from request config
  if (!accessToken && requestConfig?.headers) {
    const authHeader =
      (requestConfig.headers as Record<string, string>)?.['Authorization'] ||
      (requestConfig.headers as Record<string, string>)?.['authorization']
    if (authHeader && authHeader.startsWith('Bearer ')) {
      accessToken = authHeader.substring(7)
    }
  }

  // Clear local storage first (optimistic logout)
  clearAuthTokens()
  clearCurrentUser()
  clearTenantId()

  // Try to invalidate tokens on server (non-blocking)
  if (refreshToken || invalidateAll || accessToken) {
    try {
      const publicClient = createPublicApiClient()

      // If we have an access token, use it for authenticated logout
      if (accessToken) {
        await publicClient.post(
          '/api/v1/auth/logout/',
          invalidateAll ? {} : { refresh_token: refreshToken || undefined },
          {
            ...requestConfig,
            headers: {
              Authorization: `Bearer ${accessToken}`,
              ...(requestConfig?.headers as Record<string, string>),
            },
          } as ExtendedFetchRequestInit
        )
      } else if (refreshToken) {
        // If no access token, try with refresh token only
        await publicClient.post('/api/v1/auth/logout/', { refresh_token: refreshToken }, {
          ...requestConfig,
          skipAuth: true,
          skipTenantId: true,
        } as ExtendedFetchRequestInit)
      }
    } catch (error) {
      // Log error but don't throw - logout should always succeed locally
      // The server-side invalidation is best-effort
      if (config.development.enableApiLogging) {
        console.warn('[Auth] Failed to invalidate tokens on server:', error)
      }
    }
  }
}

/**
 * Get current user information
 *
 * @param config - Optional Axios request config
 * @returns Current user information
 */
export async function getCurrentUser(
  config?: ExtendedFetchRequestInit
): Promise<CurrentUserResponse> {
  const response = await apiClient.get<CurrentUserResponse>('/api/v1/auth/me/', config)
  return response.data
}

/**
 * List API keys
 *
 * @param config - Optional Axios request config
 * @returns List of API keys
 */
export async function listAPIKeys(config?: ExtendedFetchRequestInit): Promise<ListAPIKeysResponse> {
  const response = await apiClient.get<ListAPIKeysResponse>('/api/v1/auth/api-keys/', config)
  return response.data
}

/**
 * Create API key
 *
 * @param data - API key creation data
 * @param config - Optional Axios request config
 * @returns Created API key (includes plaintext key shown only once)
 */
export async function createAPIKey(
  data: CreateAPIKeyRequest,
  config?: ExtendedFetchRequestInit
): Promise<CreateAPIKeyResponse> {
  const response = await apiClient.post<CreateAPIKeyResponse>(
    '/api/v1/auth/api-keys/',
    data,
    config
  )
  return response.data
}

/**
 * Delete API key
 *
 * @param id - API key ID
 * @param config - Optional Axios request config
 */
export async function deleteAPIKey(id: string, config?: ExtendedFetchRequestInit): Promise<void> {
  await apiClient.delete(`/api/v1/auth/api-keys/${id}/`, config)
}

/**
 * Active Session (Refresh Token)
 */
export interface ActiveSession {
  id: string
  created_at: string
  expires_at: string
  revoked_at: string | null
  is_current: boolean
}

/**
 * List active sessions response
 */
export interface ListActiveSessionsResponse extends Array<ActiveSession> {}

/**
 * List active sessions (refresh tokens) for current user
 *
 * @param config - Optional Axios request config
 * @returns List of active sessions
 */
export async function listActiveSessions(
  config?: ExtendedFetchRequestInit
): Promise<ListActiveSessionsResponse> {
  const response = await apiClient.get<ListActiveSessionsResponse>('/api/v1/auth/sessions/', config)
  return response.data
}

/**
 * Revoke a specific session (refresh token)
 *
 * @param sessionId - Session ID (refresh token ID)
 * @param config - Optional Axios request config
 */
export async function revokeSession(
  sessionId: string,
  config?: ExtendedFetchRequestInit
): Promise<void> {
  await apiClient.post(`/api/v1/auth/sessions/${sessionId}/revoke/`, {}, config)
}
