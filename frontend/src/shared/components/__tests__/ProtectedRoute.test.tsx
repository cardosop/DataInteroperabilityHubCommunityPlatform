/**
 * ProtectedRoute Component Tests
 *
 * Root cause addressed: auth store uses lazy init (no localStorage at module load).
 * This file still stubs useAuthStore because when run in isolation the vitest worker
 * hangs (cause unknown; lazy init removed the previous cause). Stub is minimal
 * (hook return value only); real store + setState() can be used in app and other tests.
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

  it('shows loading when isLoading is true', () => {
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
