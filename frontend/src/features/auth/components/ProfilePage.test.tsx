/**
 * ProfilePage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ProfilePage } from './ProfilePage';

describe('ProfilePage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    vi.mocked(mock.get).mockImplementation((url: string) => {
      const u = String(url);
      if (u.includes('openapi.json')) {
        return Promise.resolve({
          data: {
            openapi: '3.0.0',
            paths: {
              '/api/v1/auth/register/': { post: {} },
              '/api/v1/auth/password-reset/': { post: {} },
            },
          },
        });
      }
      if (u.includes('/auth/me/')) {
        return Promise.resolve({
          data: {
            id: 'u1',
            email: 'user@example.com',
            name: 'Test User',
            roles: ['user'],
            tenant_id: 't1',
            is_active: true,
            avatar: null,
          },
        });
      }
      return Promise.resolve({
        data: { count: 0, results: [], page: 1, page_size: 20, total_pages: 0, has_next: false, has_previous: false },
      });
    });
  });

  it('renders without crashing', async () => {
    render(<ProfilePage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /^Profile$/i })).toBeInTheDocument();
    });
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<ProfilePage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByLabelText(/^display name$/i)).toBeInTheDocument();
    });
    expect(container.querySelector('.profile-form')).toBeTruthy();
  });
});
