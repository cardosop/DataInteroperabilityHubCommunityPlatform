/**
 * NotificationDropdown — 223.1 tests.
 *
 * Renders real dropdown + real hook + real React Query; only the apiClient
 * HTTP seam is mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');
vi.mock('../../../shared/services/websocketClient', () => ({
  websocketClient: {
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    onEvent: vi.fn(() => () => {}),
  },
}));

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../../auth/store/authStore';
import { NotificationDropdown } from './NotificationDropdown';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('NotificationDropdown', () => {
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

  it('shows empty state when there are no notifications', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        count: 0,
        page: 1,
        page_size: 10,
        total_pages: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never);
    render(<NotificationDropdown onClose={() => {}} />, { wrapper: wrap(queryClient) });
    await waitFor(() => {
      expect(screen.getByText(/you're all caught up/i)).toBeInTheDocument();
    });
  });

  it('renders notification rows from the API', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        count: 2,
        page: 1,
        page_size: 10,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'n-1',
            tenant: 't1',
            user: 'u1',
            title: 'Access request approved',
            message: 'Your request was approved.',
            notification_type: 'SUCCESS',
            category: 'GOVERNANCE',
            resource_type: 'ACCESS_REQUEST',
            resource_id: 'ar-123',
            read: false,
            read_at: null,
            created_at: new Date().toISOString(),
          },
          {
            id: 'n-2',
            tenant: 't1',
            user: 'u1',
            title: 'Order rejected',
            message: 'Out of stock.',
            notification_type: 'WARNING',
            category: 'MARKETPLACE',
            resource_type: 'ORDER',
            resource_id: 'o-1',
            read: true,
            read_at: new Date().toISOString(),
            created_at: new Date().toISOString(),
          },
        ],
      },
    } as never);

    render(<NotificationDropdown onClose={() => {}} />, { wrapper: wrap(queryClient) });

    await waitFor(() => {
      expect(screen.getByTestId('notification-row-n-1')).toBeInTheDocument();
      expect(screen.getByTestId('notification-row-n-2')).toBeInTheDocument();
    });
    expect(screen.getByText('Access request approved')).toBeInTheDocument();
    expect(screen.getByText('Order rejected')).toBeInTheDocument();
  });
});
