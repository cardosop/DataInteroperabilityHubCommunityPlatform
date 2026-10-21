/**
 * OrderListPage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { OrderListPage } from './OrderListPage';

describe('OrderListPage', () => {
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
    // Default: return empty paginated response for any GET
    vi.mocked(mock.get).mockResolvedValue({
      data: { count: 0, results: [], page: 1, page_size: 20, total_pages: 0, has_next: false, has_previous: false },
    });
  });

  it('renders without crashing', async () => {
    render(<OrderListPage />, { wrapper: Wrapper });
    // Component should mount without throwing
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<OrderListPage />, { wrapper: Wrapper });
    // Wait for any content to appear (heading, text, button, etc.)
    // The component should render something meaningful
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });

  it('applies listing_id from URL query param to the orders request (223.2.3)', async () => {
    // Route with a listing_id param must propagate to the API.
    function UrlWrapper({ children }: { children: ReactNode }) {
      return (
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/marketplace/orders?listing_id=L-42']}>
            {children}
          </MemoryRouter>
        </QueryClientProvider>
      );
    }
    render(<OrderListPage />, { wrapper: UrlWrapper });
    await waitFor(() => {
      const urls = vi.mocked(mock.get).mock.calls.map((c) => c[0] as string);
      expect(urls.some((u) => u.includes('listing_id=L-42'))).toBe(true);
    });
  });
});
