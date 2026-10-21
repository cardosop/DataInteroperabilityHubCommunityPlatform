/**
 * useHealth hook tests.
 * Real useHealth and healthService; fetch mocked.
 * Scenarios: success, fetch fail (degraded).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useHealth } from './useHealth';

describe('useHealth', () => {
  let queryClient: QueryClient;
  let wrapper: ({ children }: { children: ReactNode }) => ReactNode;
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    originalFetch = globalThis.fetch;
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('should return health status on success', async () => {
    const healthData = {
      status: 'healthy' as const,
      database: 'ok',
      redis: { cache: 'ok' },
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(healthData),
    });

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(healthData);
    expect(result.current.data?.status).toBe('healthy');
  });

  it('should return degraded when fetch fails', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Fetch failed'));

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual({
      status: 'degraded',
      service: 'unknown',
    });
  });
});
