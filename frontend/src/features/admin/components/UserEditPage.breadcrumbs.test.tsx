/**
 * UserEditPage — 222.2.2 breadcrumbs smoke test.
 *
 * Real page + React Query; apiClient HTTP seam auto-mocked so `useUser` /
 * `useRoles` resolve with canned payloads.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { UserEditPage } from './UserEditPage';

describe('UserEditPage breadcrumbs', () => {
  let queryClient: QueryClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/admin/users/user-abc/edit']}>
          <Routes>
            <Route path="/admin/users/:id/edit" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (url.includes('/users/user-abc')) {
        return Promise.resolve({
          data: {
            id: 'user-abc',
            email: 'target@example.com',
            display_name: 'Target User',
            status: 'ACTIVE',
            tenant_name: 'Acme',
            roles: [],
          },
        } as never);
      }
      if (url.includes('/roles')) {
        return Promise.resolve({ data: { results: [] } } as never);
      }
      return Promise.resolve({ data: {} } as never);
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders Home → Admin → user display name breadcrumb trail', async () => {
    render(<UserEditPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByLabelText('Breadcrumb')).toBeInTheDocument();
    });
    const nav = screen.getByLabelText('Breadcrumb');
    expect(nav).toHaveTextContent(/Home/);
    expect(nav).toHaveTextContent(/Admin/);
    // Target user identity: email is the only stable identifier even when
    // display_name is blank.
    expect(nav).toHaveTextContent(/target@example\.com|Target User/);
  });
});
