/**
 * Phase 85.9 — useListings hook tests.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../services/listingService', () => ({
  listingService: {
    list: vi.fn(),
    search: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../../../shared/components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: ReactNode }) => children,
}));

import { listingService } from '../services/listingService';
import { useListings, useListing } from './useListings';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

describe('useListings', () => {
  beforeEach(() => vi.clearAllMocks());

  it('fetches listings', async () => {
    vi.mocked(listingService.list).mockResolvedValue({ results: [{ id: '1' }], count: 1 });
    const { result } = renderHook(() => useListings(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(1);
  });

  it('returns empty on undefined', async () => {
    vi.mocked(listingService.list).mockResolvedValue(undefined as never);
    const { result } = renderHook(() => useListings(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.results).toHaveLength(0);
  });

  it('passes filters to service', async () => {
    vi.mocked(listingService.list).mockResolvedValue({ results: [], count: 0 });
    renderHook(() => useListings({ status: 'PUBLISHED' }), { wrapper: createWrapper() });
    await waitFor(() => expect(listingService.list).toHaveBeenCalledWith({ status: 'PUBLISHED' }));
  });

  it('handles service error', async () => {
    vi.mocked(listingService.list).mockRejectedValue(new Error('Network'));
    const { result } = renderHook(() => useListings(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('useListing disabled when id is null', () => {
    const { result } = renderHook(() => useListing(null), { wrapper: createWrapper() });
    expect(result.current.fetchStatus).toBe('idle');
  });
});
