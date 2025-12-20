/**
 * Route Guards Tests
 *
 * Tests for AuthGuard, PermissionGuard, and RoleGuard components.
 * These are convenience wrappers around ProtectedRoute.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthGuard, PermissionGuard, RoleGuard } from '../guards'
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

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AuthGuard', () => {
  const mockUseAuth = vi.mocked(useAuth)

  beforeEach(() => {
    vi.clearAllMocks()
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
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>
      </TestWrapper>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should redirect when not authenticated', () => {
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
        <AuthGuard redirectTo="/login">
          <div>Protected Content</div>
        </AuthGuard>
      </TestWrapper>
    )

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})

describe('PermissionGuard', () => {
  const mockUseAuth = vi.mocked(useAuth)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render children when user has permission', () => {
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
        <PermissionGuard permission="write">
          <div>Protected Content</div>
        </PermissionGuard>
      </TestWrapper>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should redirect when user lacks permission', () => {
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
        <PermissionGuard permission="write" redirectTo="/unauthorized">
          <div>Protected Content</div>
        </PermissionGuard>
      </TestWrapper>
    )

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('should show message when showMessage is true', () => {
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
        <PermissionGuard permission="write" showMessage>
          <div>Protected Content</div>
        </PermissionGuard>
      </TestWrapper>
    )

    expect(screen.getByText(/access denied/i)).toBeInTheDocument()
    expect(screen.getByText(/don't have permission/i)).toBeInTheDocument()
  })
})

describe('RoleGuard', () => {
  const mockUseAuth = vi.mocked(useAuth)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render children when user has role', () => {
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
        <RoleGuard role="admin">
          <div>Protected Content</div>
        </RoleGuard>
      </TestWrapper>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should redirect when user lacks role', () => {
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
        <RoleGuard role="admin" redirectTo="/unauthorized">
          <div>Protected Content</div>
        </RoleGuard>
      </TestWrapper>
    )

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})

