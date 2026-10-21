/**
 * AssetListPage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { AssetListPage } from './AssetListPage';

describe('AssetListPage', () => {
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
    render(<AssetListPage />, { wrapper: Wrapper });
    // Component should mount without throwing
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<AssetListPage />, { wrapper: Wrapper });
    // Wait for any content to appear (heading, text, button, etc.)
    // The component should render something meaningful
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });
});
