/**
 * NotificationBell — 223.1 tests.
 *
 * Real hook + real React Query; only the apiClient HTTP seam is mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');
vi.mock('../../../shared/services/websocketClient', () => ({
  websocketClient: {
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    onEvent: vi.fn(() => () => { /* unsubscribe fn */ }),
  },
}));

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../../auth/store/authStore';
import { NotificationBell } from './NotificationBell';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('NotificationBell', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    useAuthStore.setState({
      user: {
        id: 'u1',
        email: 'u@example.com',
        name: 'U',
        roles: [],
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

  it('renders the bell button with accessible label', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { count: 0 },
    } as never);
    render(<NotificationBell />, { wrapper: wrap(queryClient) });
    const bell = await screen.findByTestId('notification-bell');
    expect(bell).toHaveAttribute('aria-label', 'Notifications');
    expect(screen.queryByTestId('notification-bell-badge')).toBeNull();
  });

  it('shows badge with unread count from API', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { count: 7 },
    } as never);
    render(<NotificationBell />, { wrapper: wrap(queryClient) });
    await waitFor(() => {
      expect(screen.getByTestId('notification-bell-badge')).toHaveTextContent('7');
    });
    expect(screen.getByTestId('notification-bell')).toHaveAttribute(
      'aria-label',
      'Notifications, 7 unread',
    );
  });

  it('caps badge at 99+', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { count: 250 },
    } as never);
    render(<NotificationBell />, { wrapper: wrap(queryClient) });
    await waitFor(() => {
      expect(screen.getByTestId('notification-bell-badge')).toHaveTextContent('99+');
    });
  });

  it('opens the dropdown on click', async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.getClient().get).mockImplementation((url: string) => {
      if (url.includes('unread-count')) {
        return Promise.resolve({ data: { count: 2 } } as never);
      }
      return Promise.resolve({
        data: {
          count: 0,
          page: 1,
          page_size: 10,
          total_pages: 1,
          next: null,
          previous: null,
          results: [],
        },
      } as never);
    });
    render(<NotificationBell />, { wrapper: wrap(queryClient) });
    await user.click(await screen.findByTestId('notification-bell'));
    expect(screen.getByTestId('notification-dropdown')).toBeInTheDocument();
  });
});
