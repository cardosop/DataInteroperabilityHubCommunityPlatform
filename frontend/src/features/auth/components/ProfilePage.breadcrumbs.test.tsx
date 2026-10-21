/**
 * ProfilePage — 222.2.2 breadcrumbs gap-closure test.
 *
 * Real page + real authService/useAuthStore; only the shared apiClient HTTP
 * seam is auto-mocked so `authService.fetchUser()` resolves.
 */
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../store/authStore';
import { ProfilePage } from './ProfilePage';

describe('ProfilePage breadcrumbs', () => {
  function Wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter>{children}</MemoryRouter>;
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        id: 'u1',
        email: 'me@example.com',
        name: 'Me',
        roles: [],
        tenant_id: 't1',
        is_active: true,
        display_name: 'Me',
      },
    } as never);
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

  it('renders Home → Settings → Profile', async () => {
    render(<ProfilePage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument();
    });
    const nav = screen.getByLabelText('Breadcrumb');
    expect(nav).toHaveTextContent(/Home/);
    expect(nav).toHaveTextContent(/Settings/);
    expect(nav).toHaveTextContent(/Profile/);
  });
});
