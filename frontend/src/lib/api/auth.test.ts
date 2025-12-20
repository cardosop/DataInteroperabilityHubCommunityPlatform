/**
 * Authentication Service Tests
 *
 * Comprehensive tests for the authentication service covering:
 * - Token management (get, set, clear)
 * - Token expiration handling
 * - Automatic token refresh
 * - Login and logout operations
 * - Tenant ID management
 * - Error handling
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { AxiosError } from 'axios'
import {
  getAuthToken,
  getRefreshToken,
  getTokenExpiresAt,
  isTokenExpired,
  setAuthTokens,
  clearAuthTokens,
  getTenantId,
  setTenantId,
  clearTenantId,
  getStoredUser,
  setCurrentUser,
  clearCurrentUser,
  getAuthState,
  refreshAuthToken,
  login,
  logout,
  isAuthenticated,
  getValidAuthToken,
  AuthenticationError,
} from './auth'
import { createPublicApiClient } from './client'

// Mock the API client
vi.mock('./client', () => ({
  createPublicApiClient: vi.fn(),
}))

// Mock config
vi.mock('../config', () => ({
  config: {
    development: {
      enableApiLogging: false,
    },
  },
}))

describe('Authentication Service', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Clean up localStorage after each test
    localStorage.clear()
  })

  describe('Token Management', () => {
    describe('getAuthToken', () => {
      it('should return null when no token is stored', () => {
        expect(getAuthToken()).toBeNull()
      })

      it('should return stored access token', () => {
        localStorage.setItem('auth_access_token', 'test-token')
        expect(getAuthToken()).toBe('test-token')
      })

      it('should return null in SSR environment', () => {
        const originalWindow = global.window
        // @ts-expect-error - Testing SSR behavior
        global.window = undefined

        expect(getAuthToken()).toBeNull()

        global.window = originalWindow
      })
    })

    describe('getRefreshToken', () => {
      it('should return null when no refresh token is stored', () => {
        expect(getRefreshToken()).toBeNull()
      })

      it('should return stored refresh token', () => {
        localStorage.setItem('auth_refresh_token', 'refresh-token')
        expect(getRefreshToken()).toBe('refresh-token')
      })
    })

    describe('getTokenExpiresAt', () => {
      it('should return null when no expiration is stored', () => {
        expect(getTokenExpiresAt()).toBeNull()
      })

      it('should return stored expiration timestamp', () => {
        const expiresAt = Date.now() + 3600000
        localStorage.setItem('auth_token_expires_at', expiresAt.toString())
        expect(getTokenExpiresAt()).toBe(expiresAt)
      })
    })

    describe('isTokenExpired', () => {
      it('should return true when no expiration is stored', () => {
        expect(isTokenExpired()).toBe(true)
      })

      it('should return false when token is not expired', () => {
        const expiresAt = Date.now() + 3600000 // 1 hour from now
        localStorage.setItem('auth_token_expires_at', expiresAt.toString())
        expect(isTokenExpired()).toBe(false)
      })

      it('should return true when token is expired', () => {
        const expiresAt = Date.now() - 1000 // 1 second ago
        localStorage.setItem('auth_token_expires_at', expiresAt.toString())
        expect(isTokenExpired()).toBe(true)
      })

      it('should return true when token expires within buffer time', () => {
        const bufferSeconds = 60
        const expiresAt = Date.now() + bufferSeconds * 500 // 30 seconds from now (within buffer)
        localStorage.setItem('auth_token_expires_at', expiresAt.toString())
        expect(isTokenExpired(bufferSeconds)).toBe(true)
      })

      it('should use custom buffer time', () => {
        const bufferSeconds = 120
        const expiresAt = Date.now() + 90000 // 90 seconds from now
        localStorage.setItem('auth_token_expires_at', expiresAt.toString())
        expect(isTokenExpired(bufferSeconds)).toBe(true)
        expect(isTokenExpired(60)).toBe(false)
      })
    })

    describe('setAuthTokens', () => {
      it('should store access token, refresh token, and expiration', () => {
        setAuthTokens('access-token', 'refresh-token', 3600)

        expect(localStorage.getItem('auth_access_token')).toBe('access-token')
        expect(localStorage.getItem('auth_refresh_token')).toBe('refresh-token')
        const expiresAt = localStorage.getItem('auth_token_expires_at')
        expect(expiresAt).toBeTruthy()
        expect(parseInt(expiresAt!, 10)).toBeGreaterThan(Date.now())
      })

      it('should calculate expiration correctly', () => {
        const before = Date.now()
        setAuthTokens('access-token', 'refresh-token', 3600)
        const after = Date.now()

        const expiresAt = parseInt(
          localStorage.getItem('auth_token_expires_at')!,
          10
        )
        const expectedExpiresAt = before + 3600000

        expect(expiresAt).toBeGreaterThanOrEqual(expectedExpiresAt)
        expect(expiresAt).toBeLessThanOrEqual(after + 3600000)
      })

      it('should not store tokens in SSR environment', () => {
        const originalWindow = global.window
        // @ts-expect-error - Testing SSR behavior
        global.window = undefined

        setAuthTokens('access-token', 'refresh-token', 3600)

        global.window = originalWindow
        // Should not have stored anything
        expect(localStorage.getItem('auth_access_token')).toBeNull()
      })
    })

    describe('clearAuthTokens', () => {
      it('should clear all token-related storage', () => {
        localStorage.setItem('auth_access_token', 'token')
        localStorage.setItem('auth_refresh_token', 'refresh')
        localStorage.setItem('auth_token_expires_at', '123456')
        localStorage.setItem('auth_tenant_id', 'tenant-123')
        localStorage.setItem('auth_user', '{"id":"1"}')

        clearAuthTokens()

        expect(localStorage.getItem('auth_access_token')).toBeNull()
        expect(localStorage.getItem('auth_refresh_token')).toBeNull()
        expect(localStorage.getItem('auth_token_expires_at')).toBeNull()
        expect(localStorage.getItem('auth_tenant_id')).toBeNull()
        expect(localStorage.getItem('auth_user')).toBeNull()
      })
    })
  })

  describe('Tenant ID Management', () => {
    describe('getTenantId', () => {
      it('should return null when no tenant ID is stored', () => {
        expect(getTenantId()).toBeNull()
      })

      it('should return stored tenant ID', () => {
        localStorage.setItem('auth_tenant_id', 'tenant-123')
        expect(getTenantId()).toBe('tenant-123')
      })
    })

    describe('setTenantId', () => {
      it('should store tenant ID', () => {
        setTenantId('tenant-123')
        expect(localStorage.getItem('auth_tenant_id')).toBe('tenant-123')
      })
    })

    describe('clearTenantId', () => {
      it('should remove tenant ID from storage', () => {
        localStorage.setItem('auth_tenant_id', 'tenant-123')
        clearTenantId()
        expect(localStorage.getItem('auth_tenant_id')).toBeNull()
      })
    })
  })

  describe('User Management', () => {
    const mockUser = {
      id: 'user-123',
      email: 'test@example.com',
      name: 'Test User',
      roles: ['user'],
      permissions: ['read'],
      tenantId: 'tenant-123',
    }

    describe('getStoredUser', () => {
      it('should return null when no user is stored', () => {
        expect(getStoredUser()).toBeNull()
      })

      it('should return stored user', () => {
        localStorage.setItem('auth_user', JSON.stringify(mockUser))
        expect(getStoredUser()).toEqual(mockUser)
      })

      it('should return null for invalid JSON', () => {
        localStorage.setItem('auth_user', 'invalid-json')
        expect(getStoredUser()).toBeNull()
      })
    })

    describe('setCurrentUser', () => {
      it('should store user object', () => {
        setCurrentUser(mockUser)
        const stored = localStorage.getItem('auth_user')
        expect(stored).toBeTruthy()
        expect(JSON.parse(stored!)).toEqual(mockUser)
      })
    })

    describe('clearCurrentUser', () => {
      it('should remove user from storage', () => {
        localStorage.setItem('auth_user', JSON.stringify(mockUser))
        clearCurrentUser()
        expect(localStorage.getItem('auth_user')).toBeNull()
      })
    })
  })

  describe('getAuthState', () => {
    it('should return complete authentication state', () => {
      setAuthTokens('access-token', 'refresh-token', 3600)
      setTenantId('tenant-123')
      setCurrentUser({
        id: 'user-123',
        email: 'test@example.com',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-123',
      })

      const state = getAuthState()

      expect(state.accessToken).toBe('access-token')
      expect(state.refreshToken).toBe('refresh-token')
      expect(state.tenantId).toBe('tenant-123')
      expect(state.user).toBeTruthy()
      expect(state.isAuthenticated).toBe(true)
    })

    it('should return unauthenticated state when no tokens', () => {
      const state = getAuthState()

      expect(state.accessToken).toBeNull()
      expect(state.refreshToken).toBeNull()
      expect(state.tenantId).toBeNull()
      expect(state.user).toBeNull()
      expect(state.isAuthenticated).toBe(false)
    })

    it('should return unauthenticated when token is expired', () => {
      const expiresAt = Date.now() - 1000
      localStorage.setItem('auth_access_token', 'token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      const state = getAuthState()

      expect(state.isAuthenticated).toBe(false)
    })
  })

  describe('isAuthenticated', () => {
    it('should return false when no token', () => {
      expect(isAuthenticated()).toBe(false)
    })

    it('should return false when token is expired', () => {
      const expiresAt = Date.now() - 1000
      localStorage.setItem('auth_access_token', 'token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      expect(isAuthenticated()).toBe(false)
    })

    it('should return true when token is valid', () => {
      const expiresAt = Date.now() + 3600000
      localStorage.setItem('auth_access_token', 'token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      expect(isAuthenticated()).toBe(true)
    })
  })

  describe('refreshAuthToken', () => {
    it('should refresh token successfully', async () => {
      const mockClient = {
        post: vi.fn().mockResolvedValue({
          data: {
            access_token: 'new-access-token',
            token_type: 'Bearer',
            expires_in: 3600,
          },
        }),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      localStorage.setItem('auth_refresh_token', 'refresh-token')

      const newToken = await refreshAuthToken()

      expect(newToken).toBe('new-access-token')
      expect(getAuthToken()).toBe('new-access-token')
      expect(mockClient.post).toHaveBeenCalledWith(
        '/api/v1/auth/refresh/',
        { refresh_token: 'refresh-token' },
        expect.any(Object)
      )
    })

    it('should throw error when no refresh token available', async () => {
      await expect(refreshAuthToken()).rejects.toThrow(AuthenticationError)
      await expect(refreshAuthToken()).rejects.toThrow('No refresh token available')
    })

    it('should throw error when refresh token is invalid', async () => {
      const mockClient = {
        post: vi.fn().mockRejectedValue({
          response: {
            status: 401,
            data: {
              error: {
                message: 'Invalid refresh token',
                code: 'INVALID_TOKEN',
              },
            },
          },
        } as AxiosError),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      localStorage.setItem('auth_refresh_token', 'invalid-token')

      await expect(refreshAuthToken()).rejects.toThrow(AuthenticationError)
      expect(getAuthToken()).toBeNull()
      expect(getRefreshToken()).toBeNull()
    })

    it('should retry on network errors', async () => {
      const mockClient = {
        post: vi
          .fn()
          .mockRejectedValueOnce(new Error('Network error'))
          .mockResolvedValueOnce({
            data: {
              access_token: 'new-access-token',
              token_type: 'Bearer',
              expires_in: 3600,
            },
          }),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      localStorage.setItem('auth_refresh_token', 'refresh-token')

      const newToken = await refreshAuthToken({ maxRetries: 3 })

      expect(newToken).toBe('new-access-token')
      expect(mockClient.post).toHaveBeenCalledTimes(2)
    })

    it('should not refresh if token is not expired and force is false', async () => {
      const expiresAt = Date.now() + 3600000
      localStorage.setItem('auth_access_token', 'valid-token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      const token = await refreshAuthToken({ force: false })

      expect(token).toBe('valid-token')
      expect(createPublicApiClient).not.toHaveBeenCalled()
    })

    it('should refresh if force is true even when token is not expired', async () => {
      const mockClient = {
        post: vi.fn().mockResolvedValue({
          data: {
            access_token: 'new-access-token',
            token_type: 'Bearer',
            expires_in: 3600,
          },
        }),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      const expiresAt = Date.now() + 3600000
      localStorage.setItem('auth_access_token', 'valid-token')
      localStorage.setItem('auth_refresh_token', 'refresh-token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      const token = await refreshAuthToken({ force: true })

      expect(token).toBe('new-access-token')
      expect(mockClient.post).toHaveBeenCalled()
    })
  })

  describe('login', () => {
    it('should login successfully and store tokens', async () => {
      const mockLoginResponse = {
        data: {
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          token_type: 'Bearer',
          expires_in: 3600,
          user: {
            id: 'user-123',
            email: 'test@example.com',
            name: 'Test User',
            tenant_id: 'tenant-123',
            roles: ['user'],
            permissions: ['read'],
          },
        },
      }

      const mockMeResponse = {
        data: {
          id: 'user-123',
          email: 'test@example.com',
          name: 'Test User',
          tenant_id: 'tenant-123',
          roles: ['user'],
          permissions: ['read'],
          created_at: '2024-01-01T00:00:00Z',
        },
      }

      const mockClient = {
        post: vi.fn().mockResolvedValue(mockLoginResponse),
        get: vi.fn().mockResolvedValue(mockMeResponse),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      const result = await login({
        email: 'test@example.com',
        password: 'password123',
      })

      expect(result).toEqual(mockLoginResponse.data)
      expect(getAuthToken()).toBe('access-token')
      expect(getRefreshToken()).toBe('refresh-token')
      expect(getTenantId()).toBe('tenant-123')
      expect(getCurrentUser()).toBeTruthy()
      expect(mockClient.post).toHaveBeenCalledWith(
        '/api/v1/auth/login/',
        { email: 'test@example.com', password: 'password123' },
        expect.any(Object)
      )
      expect(mockClient.get).toHaveBeenCalledWith(
        '/api/v1/auth/me/',
        expect.any(Object)
      )
    })

    it('should handle login failure gracefully', async () => {
      const mockClient = {
        post: vi.fn().mockRejectedValue({
          response: {
            status: 401,
            data: {
              error: {
                message: 'Invalid email or password',
                code: 'INVALID_CREDENTIALS',
              },
            },
          },
        } as AxiosError),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      await expect(
        login({ email: 'test@example.com', password: 'wrong' })
      ).rejects.toThrow(AuthenticationError)

      expect(getAuthToken()).toBeNull()
    })

    it('should use login response user data if /me fails', async () => {
      const mockLoginResponse = {
        data: {
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          token_type: 'Bearer',
          expires_in: 3600,
          user: {
            id: 'user-123',
            email: 'test@example.com',
            tenant_id: 'tenant-123',
          },
        },
      }

      const mockClient = {
        post: vi.fn().mockResolvedValue(mockLoginResponse),
        get: vi.fn().mockRejectedValue(new Error('Failed to fetch user')),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      await login({
        email: 'test@example.com',
        password: 'password123',
      })

      const user = getStoredUser()
      expect(user).toBeTruthy()
      expect(user?.id).toBe('user-123')
      expect(user?.email).toBe('test@example.com')
    })
  })

  describe('logout', () => {
    it('should clear all auth data and call logout endpoint', async () => {
      setAuthTokens('access-token', 'refresh-token', 3600)
      setTenantId('tenant-123')
      setCurrentUser({
        id: 'user-123',
        email: 'test@example.com',
        roles: [],
        permissions: [],
      })

      const mockClient = {
        post: vi.fn().mockResolvedValue({ data: {} }),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      await logout()

      expect(getAuthToken()).toBeNull()
      expect(getRefreshToken()).toBeNull()
      expect(getTenantId()).toBeNull()
      expect(getStoredUser()).toBeNull()
      expect(mockClient.post).toHaveBeenCalledWith(
        '/api/v1/auth/logout/',
        { refresh_token: 'refresh-token' },
        expect.any(Object)
      )
    })

    it('should clear auth data even if logout endpoint fails', async () => {
      setAuthTokens('access-token', 'refresh-token', 3600)

      const mockClient = {
        post: vi.fn().mockRejectedValue(new Error('Network error')),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      await logout()

      // Should still clear local data
      expect(getAuthToken()).toBeNull()
      expect(getRefreshToken()).toBeNull()
    })

    it('should invalidate all tokens when invalidateAll is true', async () => {
      setAuthTokens('access-token', 'refresh-token', 3600)

      const mockClient = {
        post: vi.fn().mockResolvedValue({ data: {} }),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      await logout(true)

      expect(mockClient.post).toHaveBeenCalledWith(
        '/api/v1/auth/logout/',
        {},
        expect.any(Object)
      )
    })
  })

  describe('getValidAuthToken', () => {
    it('should return token when valid', async () => {
      const expiresAt = Date.now() + 3600000
      localStorage.setItem('auth_access_token', 'valid-token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      const token = await getValidAuthToken()

      expect(token).toBe('valid-token')
    })

    it('should refresh token when expired', async () => {
      const mockClient = {
        post: vi.fn().mockResolvedValue({
          data: {
            access_token: 'new-token',
            token_type: 'Bearer',
            expires_in: 3600,
          },
        }),
      }

      vi.mocked(createPublicApiClient).mockReturnValue(
        mockClient as any
      )

      const expiresAt = Date.now() - 1000
      localStorage.setItem('auth_access_token', 'expired-token')
      localStorage.setItem('auth_refresh_token', 'refresh-token')
      localStorage.setItem('auth_token_expires_at', expiresAt.toString())

      const token = await getValidAuthToken()

      expect(token).toBe('new-token')
    })

    it('should return null when not authenticated and no refresh token', async () => {
      const token = await getValidAuthToken()
      expect(token).toBeNull()
    })
  })
})

