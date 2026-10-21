/**
 * Phase 85.13 — useMarketplaceSyncJobs hook tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/marketplaceSyncJobService', () => ({
  marketplaceSyncJobService: {
    list: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    cancel: vi.fn(),
  },
}));

vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { marketplaceSyncJobService } from '../services/marketplaceSyncJobService';
import { useMarketplaceSyncJobs, useMarketplaceSyncJob } from './useMarketplaceSyncJobs';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useMarketplaceSyncJobs', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches sync jobs', async () => {
    vi.mocked(marketplaceSyncJobService.list).mockResolvedValue({
      results: [{ id: 'j1', status: 'COMPLETED' }], count: 1,
    });
    const { result } = renderHook(() => useMarketplaceSyncJobs(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
  });

  it('passes filters', async () => {
    vi.mocked(marketplaceSyncJobService.list).mockResolvedValue({ results: [], count: 0 });
    renderHook(
      () => useMarketplaceSyncJobs({ connection_id: 'c1' }),
      { wrapper: createWrapper() },
    );
    await waitFor(() =>
      expect(marketplaceSyncJobService.list).toHaveBeenCalledWith({ connection_id: 'c1' }),
    );
  });

  it('handles error', async () => {
    vi.mocked(marketplaceSyncJobService.list).mockRejectedValue(new Error('fail'));
    const { result } = renderHook(() => useMarketplaceSyncJobs(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('detail disabled when null', () => {
    const { result } = renderHook(() => useMarketplaceSyncJob(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('detail fetches by id', async () => {
    vi.mocked(marketplaceSyncJobService.getById).mockResolvedValue({ id: 'j1', status: 'COMPLETED' });
    const { result } = renderHook(() => useMarketplaceSyncJob('j1'), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe('j1');
  });
});
