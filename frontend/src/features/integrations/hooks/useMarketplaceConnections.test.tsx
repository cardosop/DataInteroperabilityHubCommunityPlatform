/**
 * Phase 85.12 — useMarketplaceConnections hook tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/marketplaceConnectionService', () => ({
  marketplaceConnectionService: {
    list: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    partialUpdate: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
  },
}));

vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { marketplaceConnectionService } from '../services/marketplaceConnectionService';
import { useMarketplaceConnections, useMarketplaceConnection } from './useMarketplaceConnections';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useMarketplaceConnections', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches connections', async () => {
    vi.mocked(marketplaceConnectionService.list).mockResolvedValue({
      results: [{ id: 'c1' }], count: 1, page: 1, page_size: 50,
      total_pages: 1, has_next: false, has_previous: false,
      next_page: null, previous_page: null,
    });
    const { result } = renderHook(() => useMarketplaceConnections(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
  });

  it('returns empty fallback on undefined', async () => {
    vi.mocked(marketplaceConnectionService.list).mockResolvedValue(undefined as never);
    const { result } = renderHook(() => useMarketplaceConnections(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(0);
  });

  it('handles error', async () => {
    vi.mocked(marketplaceConnectionService.list).mockRejectedValue(new Error('net'));
    const { result } = renderHook(() => useMarketplaceConnections(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('detail disabled when null', () => {
    const { result } = renderHook(() => useMarketplaceConnection(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('detail fetches by id', async () => {
    vi.mocked(marketplaceConnectionService.getById).mockResolvedValue({ id: 'c1' });
    const { result } = renderHook(() => useMarketplaceConnection('c1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('c1');
  });
});
