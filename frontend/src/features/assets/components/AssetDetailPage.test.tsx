/**
 * AssetDetailPage smoke test — Phase 106
 */
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('axios', () => {
  const inst = {
    get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  };
  return { default: { create: vi.fn(() => inst) } };
});

import { apiClient } from '../../../shared/api/client';
import { AssetDetailPage } from './AssetDetailPage';

describe('AssetDetailPage', () => {
  let queryClient: QueryClient;
  let mock: AxiosInstance;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/assets/test-uuid-123']}>
          <Routes>
            <Route path="/assets/:id" element={children} />
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
    render(<AssetDetailPage />, { wrapper: Wrapper });
    expect(document.body.innerHTML.length).toBeGreaterThan(0);
  });

  it('mounts and processes initial render cycle', async () => {
    const { container } = render(<AssetDetailPage />, { wrapper: Wrapper });
    // Component should mount and start its render lifecycle
    // (loading state, data fetch, or static content)
    expect(container.children.length).toBeGreaterThan(0);
  });
});
