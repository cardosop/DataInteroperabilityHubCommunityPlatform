/**
 * AdminPage — 222.2.2 breadcrumbs smoke test.
 *
 * Real AdminPage, real useAuthStore; only the shared apiClient HTTP seam is
 * auto-mocked so admin list calls do not hit a real backend.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../../auth/store/authStore';
import { AdminPage } from './AdminPage';

describe('AdminPage breadcrumbs', () => {
  let queryClient: QueryClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { results: [], count: 0 },
    } as never);
    useAuthStore.setState({
      user: {
        id: 'u1',
        email: 'admin@example.com',
        name: 'Admin',
        roles: ['TENANT_ADMIN'],
        tenant_id: 't1',
        is_active: true,
      },
      active_tenant_id: null,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });
  });

  afterEach(() => {
    useAuthStore.setState({
      user: null,
      active_tenant_id: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
  });

  it('renders a Breadcrumbs nav with Home → Admin', () => {
    render(<AdminPage />, { wrapper: Wrapper });

    const nav = screen.getByLabelText('Breadcrumb');
    expect(nav).toBeInTheDocument();
    expect(nav).toHaveTextContent(/Home/);
    expect(nav).toHaveTextContent(/Admin/);
  });
});
