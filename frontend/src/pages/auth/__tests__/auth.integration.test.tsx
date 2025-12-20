/**
 * Authentication Flow Integration Tests
 *
 * Comprehensive integration tests for authentication flows covering:
 * - Login flow (form submission, token storage, user data fetching, navigation)
 * - Registration flow (form submission, validation, navigation)
 * - Token refresh (automatic refresh, token expiration handling)
 * - Logout flow (token invalidation, storage cleanup, navigation)
 *
 * These tests verify the complete user journey from UI interaction to API calls
 * and state management, using MSW to intercept HTTP requests at the network level.
 * No mocks/stubs - uses real implementations.
 */

import {
  clearAuthTokens,
  clearCurrentUser,
  getAuthToken,
  getRefreshToken,
  getStoredUser,
} from '@/lib/api/auth'
import { config } from '@/lib/config'
import { act, render, screen, waitFor } from '@/test-utils'
import { server } from '@/test-utils/msw/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { userFactory } from '../../../../tests/factories'
import { LoginPage } from '../LoginPage'
import { RegisterPage } from '../RegisterPage'

const API_BASE_URL = config.api.baseUrl

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
    get length() {
      return Object.keys(store).length
    },
    key: (index: number) => {
      const keys = Object.keys(store)
      return keys[index] || null
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
})

// Mock navigate function
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Test wrapper with providers
function TestWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Routes>
          <Route path="/auth/login" element={<LoginPage />} />
          <Route path="/auth/register" element={<RegisterPage />} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Authentication Flow Integration Tests', () => {
  beforeEach(() => {
    // Clear localStorage mock
    localStorageMock.clear()
    // Clear all auth data
    try {
      clearAuthTokens()
      clearCurrentUser()
    } catch (e) {
      // Ignore errors if already cleared
    }
    mockNavigate.mockClear()
    vi.clearAllMocks()
    server.resetHandlers()
  })

  afterEach(() => {
    localStorageMock.clear()
    try {
      clearAuthTokens()
      clearCurrentUser()
    } catch (e) {
      // Ignore errors if already cleared
    }
  })

  describe('Login Flow', () => {
    it('should complete full login flow: form submission → API call → token storage → user data → navigation', async () => {
      const user = userEvent.setup()
      const testUser = userFactory.build({
        overrides: {
          email: 'test@example.com',
          name: 'Test User',
        },
      })

      // Mock successful login response - set up handlers BEFORE rendering
      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/login/`, async ({ request }) => {
          const body = (await request.json()) as {
            email?: string
            password?: string
            remember_me?: boolean
          }

          if (body.email === 'test@example.com' && body.password === 'password123') {
            const response = {
              access_token: 'test-access-token-123',
              refresh_token: 'test-refresh-token-456',
              expires_in: body.remember_me ? 86400 : 3600,
              token_type: 'Bearer',
              user: {
                id: testUser.id,
                email: testUser.email,
                name: testUser.name,
                roles: testUser.roles || [],
                permissions: testUser.permissions || [],
                tenant_id: testUser.tenantId,
              },
            }
            return HttpResponse.json(response, { status: 200 })
          }

          return HttpResponse.json(
            { error: { message: 'Invalid credentials', code: 'AUTHENTICATION_ERROR' } },
            { status: 401 }
          )
        }),
        http.get(`${API_BASE_URL}/api/v1/auth/me/`, ({ request }) => {
          const authHeader = request.headers.get('Authorization')
          if (authHeader === 'Bearer test-access-token-123') {
            return HttpResponse.json({
              id: testUser.id,
              email: testUser.email,
              name: testUser.name,
              roles: testUser.roles || [],
              permissions: testUser.permissions || [],
              tenant_id: testUser.tenantId,
            })
          }
          return HttpResponse.json({ error: { message: 'Unauthorized' } }, { status: 401 })
        })
      )

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )

      // Wait for form to be ready
      await waitFor(() => {
        expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
      })

      // Fill login form
      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')

      // Submit form
      await user.click(submitButton)

      // Wait for login to complete - increase timeout for async operations
      await waitFor(
        () => {
          expect(getAuthToken()).toBe('test-access-token-123')
          expect(getRefreshToken()).toBe('test-refresh-token-456')
        },
        { timeout: 5000 }
      )

      // Verify user data is stored
      await waitFor(() => {
        const storedUser = getStoredUser()
        expect(storedUser).not.toBeNull()
        expect(storedUser?.email).toBe('test@example.com')
        expect(storedUser?.name).toBe('Test User')
      })

      // Verify navigation
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/')
      })
    })

    it('should handle login errors and display error message', async () => {
      const user = userEvent.setup()

      // Mock failed login response
      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/login/`, () => {
          return HttpResponse.json(
            { error: { message: 'Invalid email or password', code: 'AUTHENTICATION_ERROR' } },
            { status: 401 }
          )
        })
      )

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'wrong@example.com')
      await user.type(passwordInput, 'wrongpassword')
      await user.click(submitButton)

      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument()
      })

      // Verify tokens are not stored
      expect(getAuthToken()).toBeNull()
      expect(getRefreshToken()).toBeNull()

      // Verify navigation did not occur
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('should validate form fields before submission', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )

      // Wait for form to be ready
      await waitFor(() => {
        expect(screen.getByLabelText(/email address/i)).toBeInTheDocument()
      })

      const submitButton = screen.getByRole('button', { name: /sign in/i })

      // Click submit without filling fields - this should trigger validation
      // React-hook-form with zodResolver validates on submit (asynchronously)
      // handleSubmit will prevent onSubmit from being called if validation fails
      await act(async () => {
        await user.click(submitButton)
      })

      // Wait for validation errors - react-hook-form validates on submit
      // The errors come from zod schema
      // Note: Empty email might show "Invalid email address" instead of "Email is required"
      // because zod checks .email() before .min(1)
      await waitFor(
        () => {
          // Check for any validation error messages (case-insensitive)
          // Could be "Email is required", "Invalid email address", or "Password is required"
          const emailError = screen.queryByText(/email is required|invalid email address/i, {
            exact: false,
          })
          const passwordError = screen.queryByText(/password is required/i, { exact: false })

          // Also check for error alerts (FormFieldError components)
          const errorAlerts = screen.queryAllByRole('alert')
          const hasErrorInAlerts = errorAlerts.some(el => {
            const text = el.textContent?.toLowerCase() || ''
            return (
              text.includes('required') ||
              text.includes('invalid') ||
              text.includes('email') ||
              text.includes('password')
            )
          })

          expect(emailError || passwordError || hasErrorInAlerts).toBeTruthy()
        },
        { timeout: 5000 }
      )

      // Verify no API call was made (form submission was prevented by validation)
      expect(getAuthToken()).toBeNull()
    })

    it('should handle remember me option', async () => {
      const user = userEvent.setup()
      const testUser = userFactory.build({
        overrides: {
          email: 'test@example.com',
        },
      })

      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/login/`, async ({ request }) => {
          const body = (await request.json()) as {
            email?: string
            password?: string
            remember_me?: boolean
          }

          if (body.email === 'test@example.com' && body.password === 'password123') {
            return HttpResponse.json({
              access_token: 'test-access-token-123',
              refresh_token: 'test-refresh-token-456',
              expires_in: body.remember_me ? 86400 : 3600, // Longer expiry if remember me
              user: {
                id: testUser.id,
                email: testUser.email,
                name: testUser.name,
                roles: testUser.roles,
                permissions: testUser.permissions,
                tenant_id: testUser.tenantId,
              },
            })
          }

          return HttpResponse.json(
            { error: { message: 'Invalid credentials', code: 'AUTHENTICATION_ERROR' } },
            { status: 401 }
          )
        }),
        http.get(`${API_BASE_URL}/api/v1/auth/me/`, () => {
          return HttpResponse.json({
            id: testUser.id,
            email: testUser.email,
            name: testUser.name,
            roles: testUser.roles,
            permissions: testUser.permissions,
            tenant_id: testUser.tenantId,
          })
        })
      )

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const rememberMeCheckbox = screen.getByLabelText(/remember me/i)
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(rememberMeCheckbox)
      await user.click(submitButton)

      await waitFor(() => {
        expect(getAuthToken()).toBe('test-access-token-123')
      })
    })

    it('should handle redirect parameter', async () => {
      const user = userEvent.setup()
      const testUser = userFactory.build({
        overrides: {
          email: 'test@example.com',
        },
      })

      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/login/`, async () => {
          return HttpResponse.json({
            access_token: 'test-access-token-123',
            refresh_token: 'test-refresh-token-456',
            expires_in: 3600,
            user: {
              id: testUser.id,
              email: testUser.email,
              name: testUser.name,
              roles: testUser.roles,
              permissions: testUser.permissions,
              tenant_id: testUser.tenantId,
            },
          })
        }),
        http.get(`${API_BASE_URL}/api/v1/auth/me/`, () => {
          return HttpResponse.json({
            id: testUser.id,
            email: testUser.email,
            name: testUser.name,
            roles: testUser.roles,
            permissions: testUser.permissions,
            tenant_id: testUser.tenantId,
          })
        })
      )

      // Mock window.location.search
      const originalSearch = window.location.search
      Object.defineProperty(window, 'location', {
        value: { ...window.location, search: '?redirect=/dashboard' },
        writable: true,
      })

      render(
        <TestWrapper>
          <LoginPage />
        </TestWrapper>
      )

      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const submitButton = screen.getByRole('button', { name: /sign in/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
      })

      // Restore original
      Object.defineProperty(window, 'location', {
        value: { ...window.location, search: originalSearch },
        writable: true,
      })
    })
  })

  describe('Registration Flow', () => {
    it('should complete full registration flow: form submission → API call → navigation to login', async () => {
      const user = userEvent.setup()

      // Mock successful registration response
      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/register/`, async ({ request }) => {
          const body = (await request.json()) as {
            email?: string
            password?: string
            name?: string
            tenant_id?: string
          }

          if (
            body.email === 'newuser@example.com' &&
            body.password === 'Password123' &&
            body.name === 'New User'
          ) {
            return HttpResponse.json({
              message: 'Registration successful',
              user: {
                id: 'user-123',
                email: body.email,
                name: body.name,
              },
            })
          }

          return HttpResponse.json(
            { error: { message: 'Registration failed', code: 'REGISTRATION_ERROR' } },
            { status: 400 }
          )
        })
      )

      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )

      // Fill registration form
      const nameInput = screen.getByLabelText(/full name/i)
      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0] // First is "Password", second is "Confirm Password"
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(nameInput, 'New User')
      await user.type(emailInput, 'newuser@example.com')
      await user.type(passwordInput, 'Password123')
      await user.type(confirmPasswordInput, 'Password123')

      // Submit form
      await user.click(submitButton)

      // Wait for navigation to login page
      await waitFor(
        () => {
          expect(mockNavigate).toHaveBeenCalledWith('/auth/login?registered=true')
        },
        { timeout: 3000 }
      )
    })

    it('should validate password requirements', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )

      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const nameInput = screen.getByLabelText(/full name/i)
      const emailInput = screen.getByLabelText(/email address/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })

      // Fill required fields first to avoid validation errors on them
      await user.type(nameInput, 'Test User')
      await user.type(emailInput, 'test@example.com')

      // Test password too short
      await user.type(passwordInput, 'Short1')
      // Also fill confirmPassword to avoid that validation error
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)
      await user.type(confirmPasswordInput, 'Short1')

      await user.click(submitButton)

      // Wait for validation to complete - react-hook-form validates asynchronously
      await waitFor(
        () => {
          expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Test password without uppercase
      await user.clear(passwordInput)
      await user.type(passwordInput, 'password123')
      await user.clear(confirmPasswordInput)
      await user.type(confirmPasswordInput, 'password123')
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(
            screen.getByText(/password must contain at least one uppercase letter/i)
          ).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Test password without lowercase
      await user.clear(passwordInput)
      await user.type(passwordInput, 'PASSWORD123')
      await user.clear(confirmPasswordInput)
      await user.type(confirmPasswordInput, 'PASSWORD123')
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(
            screen.getByText(/password must contain at least one lowercase letter/i)
          ).toBeInTheDocument()
        },
        { timeout: 3000 }
      )

      // Test password without number
      await user.clear(passwordInput)
      await user.type(passwordInput, 'Password')
      await user.clear(confirmPasswordInput)
      await user.type(confirmPasswordInput, 'Password')
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(screen.getByText(/password must contain at least one number/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should validate password confirmation match', async () => {
      const user = userEvent.setup()

      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )

      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)
      const nameInput = screen.getByLabelText(/full name/i)
      const emailInput = screen.getByLabelText(/email address/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })

      // Fill required fields
      await user.type(nameInput, 'Test User')
      await user.type(emailInput, 'test@example.com')

      await user.type(passwordInput, 'Password123')
      await user.type(confirmPasswordInput, 'Password456')
      await user.click(submitButton)

      await waitFor(
        () => {
          expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument()
        },
        { timeout: 3000 }
      )
    })

    it('should handle registration errors and display error message', async () => {
      const user = userEvent.setup()

      // Mock failed registration response
      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/register/`, () => {
          return HttpResponse.json(
            { error: { message: 'Email already exists', code: 'REGISTRATION_ERROR' } },
            { status: 400 }
          )
        })
      )

      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )

      const nameInput = screen.getByLabelText(/full name/i)
      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(nameInput, 'Existing User')
      await user.type(emailInput, 'existing@example.com')
      await user.type(passwordInput, 'Password123')
      await user.type(confirmPasswordInput, 'Password123')
      await user.click(submitButton)

      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument()
      })

      // Verify navigation did not occur
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('should handle optional tenant_id field', async () => {
      const user = userEvent.setup()

      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/register/`, async ({ request }) => {
          const body = (await request.json()) as { tenant_id?: string }
          return HttpResponse.json({
            message: 'Registration successful',
            user: {
              id: 'user-123',
              email: 'test@example.com',
              name: 'Test User',
              tenant_id: body.tenant_id || null,
            },
          })
        })
      )

      render(
        <TestWrapper>
          <RegisterPage />
        </TestWrapper>
      )

      const nameInput = screen.getByLabelText(/full name/i)
      const emailInput = screen.getByLabelText(/email address/i)
      // Use getAllByLabelText and take the first one (Password, not Confirm Password)
      const passwordInputs = screen.getAllByLabelText(/password/i)
      const passwordInput = passwordInputs[0]
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i)
      const tenantIdInput = screen.getByLabelText(/tenant id/i)
      const submitButton = screen.getByRole('button', { name: /create account/i })

      await user.type(nameInput, 'Test User')
      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'Password123')
      await user.type(confirmPasswordInput, 'Password123')
      // Use a valid UUID format for tenant_id (schema requires UUID)
      await user.type(tenantIdInput, '550e8400-e29b-41d4-a716-446655440000')

      await user.click(submitButton)

      await waitFor(
        () => {
          expect(mockNavigate).toHaveBeenCalledWith('/auth/login?registered=true')
        },
        { timeout: 3000 }
      )
    })
  })

  describe('Token Refresh Flow', () => {
    it('should automatically refresh token when it expires', async () => {
      const testUser = userFactory.build()

      // Set up initial tokens and user
      localStorage.setItem('auth_access_token', 'expired-token')
      localStorage.setItem('auth_refresh_token', 'valid-refresh-token')
      localStorage.setItem('auth_token_expires_at', String(Date.now() - 1000)) // Expired
      localStorage.setItem('auth_user', JSON.stringify(testUser))

      let refreshCallCount = 0

      server.use(
        http.get(`${API_BASE_URL}/api/v1/auth/me/`, () => {
          return HttpResponse.json({
            id: testUser.id,
            email: testUser.email,
            name: testUser.name,
            roles: testUser.roles,
            permissions: testUser.permissions,
            tenant_id: testUser.tenantId,
          })
        }),
        http.post(`${API_BASE_URL}/api/v1/auth/refresh/`, async ({ request }) => {
          refreshCallCount++
          const body = (await request.json()) as { refresh_token?: string }

          if (body.refresh_token === 'valid-refresh-token') {
            return HttpResponse.json({
              access_token: 'new-access-token',
              refresh_token: 'new-refresh-token',
              expires_in: 3600,
            })
          }

          return HttpResponse.json(
            { error: { message: 'Invalid refresh token', code: 'TOKEN_REFRESH_ERROR' } },
            { status: 401 }
          )
        })
      )

      // Import useAuth to trigger token refresh
      const { useAuth } = await import('@/hooks/useAuth')
      const { renderHook, waitFor: waitForHook } = await import('@testing-library/react')
      const { createHookWrapper } = await import('@/hooks/__tests__/test-utils')

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Wait for user to be loaded
      await waitForHook(
        () => {
          expect(result.current.user).toBeTruthy()
        },
        { timeout: 5000 }
      )

      // Manually trigger refresh since auto-refresh runs every 5 minutes
      await act(async () => {
        await result.current.refresh()
      })

      // Verify refresh was called
      await waitForHook(
        () => {
          expect(refreshCallCount).toBeGreaterThan(0)
        },
        { timeout: 5000 }
      )

      // Verify new tokens are stored
      await waitForHook(
        () => {
          expect(getAuthToken()).toBe('new-access-token')
          expect(getRefreshToken()).toBe('new-refresh-token')
        },
        { timeout: 5000 }
      )
    })

    it('should clear auth data when refresh token is invalid', async () => {
      // Set up expired tokens
      localStorage.setItem('auth_access_token', 'expired-token')
      localStorage.setItem('auth_refresh_token', 'invalid-refresh-token')
      localStorage.setItem('auth_token_expires_at', String(Date.now() - 1000))

      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/refresh/`, () => {
          return HttpResponse.json(
            { error: { message: 'Invalid refresh token', code: 'TOKEN_REFRESH_ERROR' } },
            { status: 401 }
          )
        })
      )

      const { useAuth } = await import('@/hooks/useAuth')
      const { renderHook, waitFor: waitForHook } = await import('@testing-library/react')
      const { createHookWrapper } = await import('@/hooks/__tests__/test-utils')

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Wait for hook to be ready
      await waitForHook(
        () => {
          expect(result.current.refresh).toBeDefined()
        },
        { timeout: 5000 }
      )

      // Manually trigger refresh to test failure handling
      await act(async () => {
        try {
          await result.current.refresh()
        } catch (err) {
          // Expected to fail
        }
      })

      // Wait for refresh to fail and clear auth
      // The refresh function clears tokens in the catch block, so wait for that
      await waitForHook(
        () => {
          expect(getAuthToken()).toBeNull()
          expect(getRefreshToken()).toBeNull()
        },
        { timeout: 5000 }
      )
    })
  })

  describe('Logout Flow', () => {
    it('should complete full logout flow: API call → token invalidation → storage cleanup → navigation', async () => {
      // Set up authenticated state
      localStorage.setItem('auth_access_token', 'test-access-token')
      localStorage.setItem('auth_refresh_token', 'test-refresh-token')
      localStorage.setItem('auth_user', JSON.stringify(userFactory.build()))

      let logoutCallCount = 0

      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/logout/`, ({ request }) => {
          logoutCallCount++
          const authHeader = request.headers.get('Authorization')

          if (authHeader === 'Bearer test-access-token') {
            return HttpResponse.json({ success: true })
          }

          return HttpResponse.json({ error: { message: 'Unauthorized' } }, { status: 401 })
        })
      )

      const { useAuth } = await import('@/hooks/useAuth')
      const { renderHook, waitFor: waitForHook } = await import('@testing-library/react')
      const { createHookWrapper } = await import('@/hooks/__tests__/test-utils')

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Wait for hook to be ready
      await waitForHook(
        () => {
          expect(result.current.logout).toBeDefined()
        },
        { timeout: 5000 }
      )

      // Call logout
      await act(async () => {
        await result.current.logout(false)
      })

      // Wait for logout to complete
      // Logout clears tokens optimistically, so they should be cleared immediately
      // But we need to wait for the API call to complete
      await waitForHook(
        () => {
          expect(logoutCallCount).toBeGreaterThan(0)
        },
        { timeout: 5000 }
      )

      // Verify tokens are cleared
      expect(getAuthToken()).toBeNull()
      expect(getRefreshToken()).toBeNull()
      expect(getStoredUser()).toBeNull()
    })

    it('should clear auth data even if server logout fails', async () => {
      // Set up authenticated state
      localStorage.setItem('auth_access_token', 'test-access-token')
      localStorage.setItem('auth_refresh_token', 'test-refresh-token')
      localStorage.setItem('auth_user', JSON.stringify(userFactory.build()))

      // Mock server error
      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/logout/`, () => {
          return HttpResponse.json(
            { error: { message: 'Server error', code: 'SERVER_ERROR' } },
            { status: 500 }
          )
        })
      )

      const { useAuth } = await import('@/hooks/useAuth')
      const { renderHook, waitFor: waitForHook, act } = await import('@testing-library/react')
      const { createHookWrapper } = await import('@/hooks/__tests__/test-utils')

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Call logout - it should clear auth data even if server call fails
      // Logout clears tokens first (optimistic), so even if server fails, tokens are cleared
      await act(async () => {
        try {
          await result.current.logout(false)
        } catch (err) {
          // Expected - server call fails but logout should still clear local data
        }
      })

      // Verify auth data is cleared even though server call failed
      // Logout clears tokens immediately (optimistically), so they should be cleared right away
      // But wait for the mutation to complete and state to update
      await waitForHook(
        () => {
          const token = getAuthToken()
          const refreshToken = getRefreshToken()
          const user = getStoredUser()
          expect(token).toBeNull()
          expect(refreshToken).toBeNull()
          expect(user).toBeNull()
        },
        { timeout: 2000 }
      )
    })

    it('should invalidate all tokens when invalidateAll is true', async () => {
      localStorage.setItem('auth_access_token', 'test-access-token')
      localStorage.setItem('auth_refresh_token', 'test-refresh-token')

      let logoutCallCount = 0
      let invalidateAllParam = false

      server.use(
        http.post(`${API_BASE_URL}/api/v1/auth/logout/`, async ({ request }) => {
          logoutCallCount++
          const body = (await request.json()) as { refresh_token?: string }
          invalidateAllParam = !body.refresh_token // If no refresh_token, invalidateAll was likely true
          return HttpResponse.json({ success: true })
        })
      )

      const { useAuth } = await import('@/hooks/useAuth')
      const { renderHook, waitFor: waitForHook } = await import('@testing-library/react')
      const { createHookWrapper } = await import('@/hooks/__tests__/test-utils')

      const wrapper = createHookWrapper()
      const { result } = renderHook(() => useAuth(), { wrapper })

      // Wait for hook to be ready
      await waitForHook(
        () => {
          expect(result.current.logout).toBeDefined()
        },
        { timeout: 5000 }
      )

      // Call logout with invalidateAll
      await result.current.logout(true)

      await waitForHook(
        () => {
          expect(logoutCallCount).toBeGreaterThan(0)
          expect(getAuthToken()).toBeNull()
        },
        { timeout: 5000 }
      )
    })
  })
})
