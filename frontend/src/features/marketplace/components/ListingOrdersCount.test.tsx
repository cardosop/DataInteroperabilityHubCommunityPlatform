/**
 * ListingOrdersCount — 223.2.3 tests.
 * Real useOrders + React Query; apiClient HTTP seam mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ListingOrdersCount } from './ListingOrdersCount';

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('ListingOrdersCount', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  });

  it('renders the order count and passes listing_id to the API', async () => {
    const getMock = vi.mocked(apiClient.getClient().get);
    getMock.mockResolvedValue({
      data: {
        count: 42,
        page: 1,
        page_size: 1,
        total_pages: 42,
        next: null,
        previous: null,
        results: [],
      },
    } as never);

    render(<ListingOrdersCount listingId="L-1" />, { wrapper: wrap(queryClient) });

    await waitFor(() => {
      expect(screen.getByTestId('listing-orders-total')).toHaveTextContent(/42/);
    });
    expect(screen.getByRole('link', { name: /view orders/i })).toHaveAttribute(
      'href',
      '/marketplace/orders?listing_id=L-1',
    );
    const url = getMock.mock.calls[0][0] as string;
    expect(url).toContain('listing_id=L-1');
  });

  it('does not render the View-orders link when there are no orders', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: {
        count: 0,
        page: 1,
        page_size: 1,
        total_pages: 0,
        next: null,
        previous: null,
        results: [],
      },
    } as never);

    render(<ListingOrdersCount listingId="L-empty" />, {
      wrapper: wrap(queryClient),
    });

    await waitFor(() => {
      expect(screen.getByTestId('listing-orders-total')).toHaveTextContent(/0 orders/);
    });
    expect(screen.queryByRole('link', { name: /view orders/i })).toBeNull();
  });
});
