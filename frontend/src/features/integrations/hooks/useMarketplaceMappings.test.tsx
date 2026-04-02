/**
 * Phase 85.14 — useMarketplaceMappings hook tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/marketplaceMappingService', () => ({
  marketplaceMappingService: {
    list: vi.fn(),
    getById: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { marketplaceMappingService } from '../services/marketplaceMappingService';
import { useMarketplaceMappings, useMarketplaceMapping } from './useMarketplaceMappings';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useMarketplaceMappings', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches mappings', async () => {
    vi.mocked(marketplaceMappingService.list).mockResolvedValue({
      results: [{ id: 'm1' }], count: 1,
    });
    const { result } = renderHook(() => useMarketplaceMappings(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
  });

  it('passes filters', async () => {
    vi.mocked(marketplaceMappingService.list).mockResolvedValue({ results: [], count: 0 });
    renderHook(
      () => useMarketplaceMappings({ connection_id: 'c2' }),
      { wrapper: createWrapper() },
    );
    await waitFor(() =>
      expect(marketplaceMappingService.list).toHaveBeenCalledWith({ connection_id: 'c2' }),
    );
  });

  it('handles error', async () => {
    vi.mocked(marketplaceMappingService.list).mockRejectedValue(new Error('fail'));
    const { result } = renderHook(() => useMarketplaceMappings(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('detail disabled when null', () => {
    const { result } = renderHook(() => useMarketplaceMapping(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('detail fetches by id', async () => {
    vi.mocked(marketplaceMappingService.getById).mockResolvedValue({ id: 'm1' });
    const { result } = renderHook(() => useMarketplaceMapping('m1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('m1');
  });
});
