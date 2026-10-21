/**
 * ProtectedRoute Component Tests
 *
 * Phase 213.I.7 — tests for synchronous auth-store hydration.
 *
 * This file stubs useAuthStore because when run in isolation the vitest worker
 * hangs (lazy init issue). Stub is minimal (hook return value only).
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProtectedRoute } from '../ProtectedRoute';

vi.mock('../../../features/auth/store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

import { useAuthStore } from '../../../features/auth/store/authStore';

const mockUseAuthStore = vi.mocked(useAuthStore);

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders children when user is authenticated', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: '1', email: 'test@example.com', name: 'Test', tenant_id: 't1', roles: ['USER'] },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('shows LoadingSpinner when isLoading is true', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: true,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    // Phase 213.I.6: verify it's a LoadingSpinner (role="status"), not a bare <div>
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('redirects to login when user is not authenticated', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  // Phase 213.I.7(a) — hydrated DE user with requiredRole: ['TENANT_ADMIN']
  // navigates to /403 on first render with NO loading state.
  it('hydrated DE user redirects to /403 on first render (no loading)', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'de@example.com',
        name: 'Data Engineer',
        tenant_id: 't1',
        roles: ['DATA_ENGINEER'],
      },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <ProtectedRoute requiredRole={['TENANT_ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    // Must redirect immediately — no "Loading..." shown
    expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
  });

  // Phase 213.I.7(b) — empty localStorage → redirect to /login on first render.
  it('empty localStorage redirects to /login on first render', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <ProtectedRoute requiredRole={['TENANT_ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
  });

  // Phase 213.I.7(c) — hydrated TENANT_ADMIN with matching role renders synchronously.
  it('hydrated TENANT_ADMIN renders children synchronously', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'admin@example.com',
        name: 'Admin',
        tenant_id: 't1',
        roles: ['USER', 'TENANT_ADMIN'],
      },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole={['TENANT_ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Content')).toBeInTheDocument();
  });

  // Phase 213.I.7(d) — regression: when the store updates with new roles
  // (background /auth/me/ refresh), ProtectedRoute re-evaluates and
  // redirects if the new role set no longer matches.
  it('re-evaluates on store update: revoked role triggers redirect', () => {
    // First render: user has TENANT_ADMIN → children render.
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'admin@example.com',
        name: 'Admin',
        tenant_id: 't1',
        roles: ['USER', 'TENANT_ADMIN'],
      },
      isLoading: false,
    } as never);

    const { rerender } = render(
      <MemoryRouter initialEntries={['/admin']}>
        <ProtectedRoute requiredRole={['TENANT_ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Content')).toBeInTheDocument();

    // Background refresh returns updated roles WITHOUT TENANT_ADMIN.
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'admin@example.com',
        name: 'Admin',
        tenant_id: 't1',
        roles: ['USER'],
      },
      isLoading: false,
    } as never);

    rerender(
      <MemoryRouter initialEntries={['/admin']}>
        <ProtectedRoute requiredRole={['TENANT_ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    // Children must no longer render after role revocation.
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
  });

  it('redirects to 403 when user lacks required role', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: '1', email: 'test@example.com', name: 'Test', tenant_id: 't1', roles: ['USER'] },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <ProtectedRoute requiredRole={['ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument();
  });

  it('renders children when user has required role', () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: {
        id: '1',
        email: 'admin@example.com',
        name: 'Admin',
        tenant_id: 't1',
        roles: ['USER', 'ADMIN'],
      },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole={['ADMIN']}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Content')).toBeInTheDocument();
  });
});
