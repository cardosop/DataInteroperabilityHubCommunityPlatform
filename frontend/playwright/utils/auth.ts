/**
 * Authentication Helpers for Playwright Tests
 *
 * Comprehensive authentication utilities for E2E tests.
 * Provides helpers for login, logout, token management, and authentication state.
 *
 * Uses real API calls - no mocks/stubs. Always fixes root cause.
 */

import { Page, APIRequestContext, expect } from '@playwright/test'

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
 * Authentication credentials for test users
 */
export interface TestCredentials {
  email: string
  password: string
  name?: string
  tenantId?: string
}

/**
 * Authentication state stored in browser context
 */
export interface AuthState {
  accessToken: string
  refreshToken: string
  user: {
    id: string
    email: string
    name?: string
    tenantId?: string
    roles?: string[]
    permissions?: string[]
  }
}

/**
 * Get API base URL from environment or default
 */
function getApiBaseUrl(): string {
  return process.env.VITE_API_BASE_URL || process.env.PLAYWRIGHT_API_BASE_URL || 'http://localhost:8000'
}

/**
 * Login user via API and set authentication state in browser
 *
 * @param page - Playwright page instance
 * @param credentials - Login credentials
 * @param apiContext - Optional API request context for direct API calls
 * @returns Authentication state with tokens and user info
 *
 * @example
 * ```ts
 * const authState = await login(page, {
 *   email: 'test@example.com',
 *   password: 'password123'
 * })
 * ```
 */
export async function login(
  page: Page,
  credentials: TestCredentials,
  apiContext?: APIRequestContext
): Promise<AuthState> {
  const apiBaseUrl = getApiBaseUrl()
  const loginUrl = `${apiBaseUrl}/api/v1/auth/login/`

  // Make login API call
  const response = await (apiContext || page.request).post(loginUrl, {
    data: {
      email: credentials.email,
      password: credentials.password,
      remember_me: credentials.tenantId ? false : undefined,
    } as LoginRequest,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Login failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  const loginResponse = (await response.json()) as LoginResponse

  if (!loginResponse.access_token || !loginResponse.refresh_token) {
    throw new Error('Login response missing tokens')
  }

  // Set authentication state in browser localStorage
  await page.addInitScript(
    ({ accessToken, refreshToken, expiresIn, user }) => {
      localStorage.setItem('auth_access_token', accessToken)
      localStorage.setItem('auth_refresh_token', refreshToken)
      if (expiresIn) {
        const expiresAt = Date.now() + expiresIn * 1000
        localStorage.setItem('auth_token_expires_at', String(expiresAt))
      }
      if (user) {
        localStorage.setItem('auth_user', JSON.stringify(user))
      }
      if (user?.tenant_id) {
        localStorage.setItem('auth_tenant_id', user.tenant_id)
      }
    },
    {
      accessToken: loginResponse.access_token,
      refreshToken: loginResponse.refresh_token,
      expiresIn: loginResponse.expires_in,
      user: loginResponse.user,
    }
  )

  // Reload page to apply authentication state
  await page.reload()
  await page.waitForLoadState('networkidle')

  return {
    accessToken: loginResponse.access_token,
    refreshToken: loginResponse.refresh_token,
    user: {
      id: loginResponse.user?.id || '',
      email: loginResponse.user?.email || credentials.email,
      name: loginResponse.user?.name,
      tenantId: loginResponse.user?.tenant_id,
      roles: loginResponse.user?.roles,
      permissions: loginResponse.user?.permissions,
    },
  }
}

/**
 * Login user via UI (form interaction)
 *
 * @param page - Playwright page instance
 * @param credentials - Login credentials
 * @param options - Additional options
 * @returns Authentication state after successful login
 *
 * @example
 * ```ts
 * const authState = await loginViaUI(page, {
 *   email: 'test@example.com',
 *   password: 'password123'
 * })
 * ```
 */
export async function loginViaUI(
  page: Page,
  credentials: TestCredentials,
  options: {
    waitForNavigation?: boolean
    redirectTo?: string
  } = {}
): Promise<AuthState> {
  const { waitForNavigation = true, redirectTo } = options

  // Navigate to login page
  await page.goto('/login' + (redirectTo ? `?redirect=${encodeURIComponent(redirectTo)}` : ''))

  // Fill login form
  await page.fill('input[type="email"], input[name="email"]', credentials.email)
  await page.fill('input[type="password"], input[name="password"]', credentials.password)

  // Submit form
  if (waitForNavigation) {
    await Promise.all([
      page.waitForURL(redirectTo || '/', { timeout: 10000 }),
      page.click('button[type="submit"], button:has-text("Sign In")'),
    ])
  } else {
    await page.click('button[type="submit"], button:has-text("Sign In")')
  }

  // Wait for authentication state to be set
  await page.waitForFunction(() => {
    return localStorage.getItem('auth_access_token') !== null
  }, { timeout: 10000 })

  // Get authentication state from localStorage
  const authState = await page.evaluate(() => {
    const accessToken = localStorage.getItem('auth_access_token')
    const refreshToken = localStorage.getItem('auth_refresh_token')
    const userStr = localStorage.getItem('auth_user')
    const user = userStr ? JSON.parse(userStr) : null

    if (!accessToken || !refreshToken) {
      return null
    }

    return {
      accessToken,
      refreshToken,
      user: user || {
        id: '',
        email: '',
      },
    }
  })

  if (!authState) {
    throw new Error('Failed to retrieve authentication state after login')
  }

  return authState as AuthState
}

/**
 * Logout user and clear authentication state
 *
 * @param page - Playwright page instance
 * @param apiContext - Optional API request context for direct API calls
 * @param invalidateAll - If true, invalidates all refresh tokens
 *
 * @example
 * ```ts
 * await logout(page)
 * ```
 */
export async function logout(
  page: Page,
  apiContext?: APIRequestContext,
  invalidateAll: boolean = false
): Promise<void> {
  const apiBaseUrl = getApiBaseUrl()
  const logoutUrl = `${apiBaseUrl}/api/v1/auth/logout/`

  // Get tokens before clearing
  const tokens = await page.evaluate(() => {
    return {
      accessToken: localStorage.getItem('auth_access_token'),
      refreshToken: localStorage.getItem('auth_refresh_token'),
    }
  })

  // Clear local storage first (optimistic logout)
  await page.evaluate(() => {
    localStorage.removeItem('auth_access_token')
    localStorage.removeItem('auth_refresh_token')
    localStorage.removeItem('auth_token_expires_at')
    localStorage.removeItem('auth_user')
    localStorage.removeItem('auth_tenant_id')
  })

  // Try to invalidate tokens on server (non-blocking)
  if (tokens.refreshToken || invalidateAll) {
    try {
      await (apiContext || page.request).post(logoutUrl, {
        data: invalidateAll ? {} : { refresh_token: tokens.refreshToken },
        headers: tokens.accessToken
          ? {
              Authorization: `Bearer ${tokens.accessToken}`,
              'Content-Type': 'application/json',
            }
          : {
              'Content-Type': 'application/json',
            },
      })
    } catch (error) {
      // Log but don't throw - logout should always succeed locally
      console.warn('[Auth] Failed to invalidate tokens on server:', error)
    }
  }

  // Reload page to apply logout state
  await page.reload()
  await page.waitForLoadState('networkidle')
}

/**
 * Register new user via API
 *
 * @param page - Playwright page instance
 * @param credentials - Registration credentials
 * @param apiContext - Optional API request context for direct API calls
 * @returns Registration response
 *
 * @example
 * ```ts
 * const response = await register(page, {
 *   email: 'newuser@example.com',
 *   password: 'Password123',
 *   name: 'New User'
 * })
 * ```
 */
export async function register(
  page: Page,
  credentials: TestCredentials,
  apiContext?: APIRequestContext
): Promise<RegisterResponse> {
  const apiBaseUrl = getApiBaseUrl()
  const registerUrl = `${apiBaseUrl}/api/v1/auth/register/`

  if (!credentials.name) {
    throw new Error('Name is required for registration')
  }

  const response = await (apiContext || page.request).post(registerUrl, {
    data: {
      email: credentials.email,
      password: credentials.password,
      name: credentials.name,
      tenant_id: credentials.tenantId,
    } as RegisterRequest,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Registration failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  return (await response.json()) as RegisterResponse
}

/**
 * Register new user via UI (form interaction)
 *
 * @param page - Playwright page instance
 * @param credentials - Registration credentials
 * @returns Registration response
 *
 * @example
 * ```ts
 * await registerViaUI(page, {
 *   email: 'newuser@example.com',
 *   password: 'Password123',
 *   name: 'New User'
 * })
 * ```
 */
export async function registerViaUI(
  page: Page,
  credentials: TestCredentials
): Promise<void> {
  if (!credentials.name) {
    throw new Error('Name is required for registration')
  }

  // Navigate to register page
  await page.goto('/auth/register')

  // Fill registration form
  await page.fill('input[name="name"]', credentials.name)
  await page.fill('input[type="email"], input[name="email"]', credentials.email)
  await page.fill('input[type="password"][name="password"]', credentials.password)
  await page.fill('input[type="password"][name="confirmPassword"]', credentials.password)

  if (credentials.tenantId) {
    await page.fill('input[name="tenant_id"]', credentials.tenantId)
  }

  // Submit form
  await Promise.all([
    page.waitForURL('/auth/login*', { timeout: 10000 }),
    page.click('button[type="submit"], button:has-text("Create Account")'),
  ])
}

/**
 * Refresh authentication token
 *
 * @param page - Playwright page instance
 * @param apiContext - Optional API request context for direct API calls
 * @returns New authentication state
 *
 * @example
 * ```ts
 * const newAuthState = await refreshToken(page)
 * ```
 */
export async function refreshToken(
  page: Page,
  apiContext?: APIRequestContext
): Promise<AuthState> {
  const apiBaseUrl = getApiBaseUrl()
  const refreshUrl = `${apiBaseUrl}/auth/refresh/`

  // Get refresh token from localStorage
  const refreshTokenValue = await page.evaluate(() => {
    return localStorage.getItem('auth_refresh_token')
  })

  if (!refreshTokenValue) {
    throw new Error('No refresh token available')
  }

  // Make refresh API call
  const response = await (apiContext || page.request).post(refreshUrl, {
    data: {
      refresh_token: refreshTokenValue,
    },
    headers: {
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Token refresh failed: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  const refreshResponse = await response.json()

  if (!refreshResponse.access_token) {
    throw new Error('Token refresh response missing access token')
  }

  // Update tokens in localStorage
  await page.evaluate(
    ({ accessToken, refreshToken, expiresIn }) => {
      localStorage.setItem('auth_access_token', accessToken)
      if (refreshToken) {
        localStorage.setItem('auth_refresh_token', refreshToken)
      }
      if (expiresIn) {
        const expiresAt = Date.now() + expiresIn * 1000
        localStorage.setItem('auth_token_expires_at', String(expiresAt))
      }
    },
    {
      accessToken: refreshResponse.access_token,
      refreshToken: refreshResponse.refresh_token || refreshTokenValue,
      expiresIn: refreshResponse.expires_in,
    }
  )

  // Get updated user info
  const userInfo = await getCurrentUser(page, apiContext)

  return {
    accessToken: refreshResponse.access_token,
    refreshToken: refreshResponse.refresh_token || refreshTokenValue,
    user: userInfo,
  }
}

/**
 * Get current authenticated user
 *
 * @param page - Playwright page instance
 * @param apiContext - Optional API request context for direct API calls
 * @returns Current user information
 *
 * @example
 * ```ts
 * const user = await getCurrentUser(page)
 * ```
 */
export async function getCurrentUser(
  page: Page,
  apiContext?: APIRequestContext
): Promise<AuthState['user']> {
  const apiBaseUrl = getApiBaseUrl()
  const meUrl = `${apiBaseUrl}/api/v1/auth/me/`

  // Get access token from localStorage
  const accessToken = await page.evaluate(() => {
    return localStorage.getItem('auth_access_token')
  })

  if (!accessToken) {
    throw new Error('No access token available')
  }

  // Make API call to get user info
  const response = await (apiContext || page.request).get(meUrl, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok()) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(
      `Failed to get current user: ${response.status()} ${response.statusText()}. ${JSON.stringify(errorBody)}`
    )
  }

  const userResponse = await response.json()

  return {
    id: userResponse.id,
    email: userResponse.email,
    name: userResponse.name,
    tenantId: userResponse.tenant_id,
    roles: userResponse.roles,
    permissions: userResponse.permissions,
  }
}

/**
 * Check if user is authenticated
 *
 * @param page - Playwright page instance
 * @returns True if user is authenticated
 *
 * @example
 * ```ts
 * const isAuth = await isAuthenticated(page)
 * ```
 */
export async function isAuthenticated(page: Page): Promise<boolean> {
  return await page.evaluate(() => {
    return localStorage.getItem('auth_access_token') !== null
  })
}

/**
 * Get authentication state from localStorage
 *
 * @param page - Playwright page instance
 * @returns Authentication state or null if not authenticated
 *
 * @example
 * ```ts
 * const authState = await getAuthState(page)
 * ```
 */
export async function getAuthState(page: Page): Promise<AuthState | null> {
  const state = await page.evaluate(() => {
    const accessToken = localStorage.getItem('auth_access_token')
    const refreshToken = localStorage.getItem('auth_refresh_token')
    const userStr = localStorage.getItem('auth_user')

    if (!accessToken || !refreshToken) {
      return null
    }

    const user = userStr ? JSON.parse(userStr) : null

    return {
      accessToken,
      refreshToken,
      user: user || {
        id: '',
        email: '',
      },
    }
  })

  return state as AuthState | null
}

/**
 * Set authentication state directly (for test setup)
 *
 * @param page - Playwright page instance
 * @param authState - Authentication state to set
 *
 * @example
 * ```ts
 * await setAuthState(page, {
 *   accessToken: 'token-123',
 *   refreshToken: 'refresh-456',
 *   user: { id: 'user-1', email: 'test@example.com' }
 * })
 * ```
 */
export async function setAuthState(page: Page, authState: AuthState): Promise<void> {
  await page.addInitScript(
    ({ accessToken, refreshToken, user }) => {
      localStorage.setItem('auth_access_token', accessToken)
      localStorage.setItem('auth_refresh_token', refreshToken)
      if (user) {
        localStorage.setItem('auth_user', JSON.stringify(user))
      }
      if (user?.tenantId) {
        localStorage.setItem('auth_tenant_id', user.tenantId)
      }
    },
    authState
  )

  await page.reload()
  await page.waitForLoadState('networkidle')
}

/**
 * Wait for authentication state to be set
 *
 * @param page - Playwright page instance
 * @param timeout - Maximum time to wait in milliseconds
 *
 * @example
 * ```ts
 * await waitForAuthentication(page, 5000)
 * ```
 */
export async function waitForAuthentication(page: Page, timeout: number = 10000): Promise<void> {
  await page.waitForFunction(
    () => localStorage.getItem('auth_access_token') !== null,
    { timeout }
  )
}

/**
 * Wait for logout to complete
 *
 * @param page - Playwright page instance
 * @param timeout - Maximum time to wait in milliseconds
 *
 * @example
 * ```ts
 * await waitForLogout(page, 5000)
 * ```
 */
export async function waitForLogout(page: Page, timeout: number = 10000): Promise<void> {
  await page.waitForFunction(
    () => localStorage.getItem('auth_access_token') === null,
    { timeout }
  )
}

