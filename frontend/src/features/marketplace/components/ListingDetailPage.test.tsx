/**
 * ListingDetailPage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../../auth/store/authStore';
import { ListingDetailPage } from './ListingDetailPage';

describe('ListingDetailPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/marketplace/listings/test-uuid-123']}>
          <Routes>
            <Route path="/marketplace/listings/:id" element={children} />
            <Route path="/marketplace/orders/:id" element={<div>Order Detail</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: {
        id: 'user-test',
        email: 'user@example.com',
        name: 'Test User',
        roles: ['DATA_CONSUMER'],
        tenant_id: 'tenant-consumer',
        is_active: true,
      },
      active_tenant_id: null,
      isAuthenticated: true,
      isLoading: false,
      error: null,
    });
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    // Default: return mock detail response for GET by ID
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        id: 'test-uuid-123',
        tenant: 'tenant-provider',
        asset: 'asset-1',
        title: 'Test Listing',
        status: 'PUBLISHED',
        pricing_model: 'REQUEST_APPROVAL',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    });
  });

  it('renders without crashing', async () => {
    render(<ListingDetailPage />, { wrapper: Wrapper });
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<ListingDetailPage />, { wrapper: Wrapper });
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('shows internal access-request path for own listing tenant', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        id: 'test-uuid-123',
        tenant: 'tenant-consumer',
        asset: 'asset-1',
        title: 'Own Listing',
        status: 'PUBLISHED',
        pricing_model: 'REQUEST_APPROVAL',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    });

    render(<ListingDetailPage />, { wrapper: Wrapper });

    await waitFor(() =>
      expect(
        screen.getByText(
          /Internal access request — requires approval from data owner\./i
        )
      ).toBeInTheDocument()
    );

    expect(screen.getByRole('button', { name: /Request Access/i })).toBeInTheDocument();
  });

  it('redirects to existing order when backend returns active-order conflict', async () => {
    vi.mocked(mock.post).mockRejectedValue({
      error: {
        code: 'CONFLICT_ERROR',
        message: 'You already have an active order for this listing.',
        http_status: 409,
        request_id: 'req-1',
        timestamp: new Date().toISOString(),
        details: {
          error: 'You already have an active order for this listing.',
          order_id: 'existing-order-123',
        },
      },
    });

    render(<ListingDetailPage />, { wrapper: Wrapper });

    const requestButton = await screen.findByRole('button', { name: /Request Access/i });
    fireEvent.click(requestButton);

    await waitFor(() => {
      expect(screen.getByText('Order Detail')).toBeInTheDocument();
    });
  });
});
