/**
 * useLineageSubscriptions — response-shape normalization (Phase 1.5).
 *
 * ``LineageSubscriptionPanel`` calls ``list?.results.find(...)``. The ``?.``
 * guards only ``list`` itself; a 200 whose body lacks an array ``results``
 * (proxy error envelope, drift) left ``results`` undefined and crashed with
 * "results.find is not a function". The hook is the service boundary for
 * react-query — normalize ``results`` here so callers get an array, always.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { useLineageSubscriptions } from './useLineageSubscriptions';

function wrapper(queryClient: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useLineageSubscriptions normalization', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('passes an array results payload through', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const subscriptions = [
      { id: 's1', severity_threshold: 'HIGH', in_app: true, email: false, slack: false },
    ];
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { count: 1, next_cursor: null, previous_cursor: null, page_size: 10, results: subscriptions },
    } as never);

    const { result } = renderHook(() => useLineageSubscriptions(), {
      wrapper: wrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.results).toEqual(subscriptions);
  });

  it('normalizes a missing results key to []', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { error: 'proxy exploded' },
    } as never);

    const { result } = renderHook(() => useLineageSubscriptions(), {
      wrapper: wrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.results).toEqual([]);
  });

  it('normalizes a non-array results value to []', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { count: 1, results: { s1: true } },
    } as never);

    const { result } = renderHook(() => useLineageSubscriptions(), {
      wrapper: wrapper(queryClient),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.results).toEqual([]);
  });
});
