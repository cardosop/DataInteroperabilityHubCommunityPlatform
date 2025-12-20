/**
 * ProtectedRoute Tests
 *
 * Comprehensive tests for the ProtectedRoute component.
 * Tests authentication, permission, and role-based route protection.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProtectedRoute } from '../ProtectedRoute'
import { useAuth } from '@/hooks/useAuth'

// Mock useAuth hook
vi.mock('@/hooks/useAuth')

const createTestQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

const TestWrapper = ({
  children,
  initialEntries,
}: {
  children: React.ReactNode
  initialEntries?: string[]
}) => {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProtectedRoute', () => {
  const mockUseAuth = vi.mocked(useAuth)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Public routes (no protection)', () => {
    it('should render children when no protection is required', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute>
            <div>Public Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Public Content')).toBeInTheDocument()
    })
  })

  describe('Authentication protection', () => {
    it('should show loading state while checking authentication', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: true,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute requireAuth>
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText(/checking authentication/i)).toBeInTheDocument()
    })

    it('should redirect to login when not authenticated', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper initialEntries={['/protected']}>
          <ProtectedRoute requireAuth redirectTo="/login">
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      // Should redirect to login
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    })

    it('should render children when authenticated', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute requireAuth>
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })
  })

  describe('Permission protection', () => {
    it('should redirect when user lacks required permission', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute
            requireAuth
            permissions="write"
            unauthorizedRedirectTo="/unauthorized"
          >
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    })

    it('should render children when user has required permission', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read', 'write'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute requireAuth permissions="write">
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })

    it('should check any permission when multiple permissions provided', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute
            requireAuth
            permissions={['read', 'write']}
            requireAllPermissions={false}
          >
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })

    it('should require all permissions when requireAllPermissions is true', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute
            requireAuth
            permissions={['read', 'write']}
            requireAllPermissions={true}
            unauthorizedRedirectTo="/unauthorized"
          >
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    })
  })

  describe('Role protection', () => {
    it('should redirect when user lacks required role', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute
            requireAuth
            roles="admin"
            unauthorizedRedirectTo="/unauthorized"
          >
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    })

    it('should render children when user has required role', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['admin'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute requireAuth roles="admin">
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })
  })

  describe('Custom components', () => {
    it('should render custom loading component when provided', () => {
      mockUseAuth.mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: true,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute
            requireAuth
            loadingComponent={<div>Custom Loading...</div>}
          >
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Custom Loading...')).toBeInTheDocument()
    })

    it('should render custom unauthorized component when provided', () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
        roles: ['user'],
        permissions: ['read'],
        tenantId: 'tenant-1',
      }

      mockUseAuth.mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        login: vi.fn(),
        logout: vi.fn(),
        register: vi.fn(),
        refresh: vi.fn(),
      })

      render(
        <TestWrapper>
          <ProtectedRoute
            requireAuth
            permissions="write"
            unauthorizedComponent={<div>Custom Unauthorized</div>}
          >
            <div>Protected Content</div>
          </ProtectedRoute>
        </TestWrapper>
      )

      expect(screen.getByText('Custom Unauthorized')).toBeInTheDocument()
    })
  })
})

