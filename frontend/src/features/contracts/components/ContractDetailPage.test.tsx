/**
 * ContractDetailPage smoke test — Phase 106
 */
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { ContractDetailPage } from './ContractDetailPage';

describe('ContractDetailPage', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/contracts/test-uuid-123']}>
          <Routes>
            <Route path="/contracts/:id" element={children} />
          </Routes>
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
    // Default: return mock detail response for GET by ID
    vi.mocked(mock.get).mockResolvedValue({
      data: { id: 'test-uuid-123', name: 'Test Item', status: 'ACTIVE', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
    });
  });

  it('renders without crashing', async () => {
    render(<ContractDetailPage />, { wrapper: Wrapper });
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<ContractDetailPage />, { wrapper: Wrapper });
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });
});
