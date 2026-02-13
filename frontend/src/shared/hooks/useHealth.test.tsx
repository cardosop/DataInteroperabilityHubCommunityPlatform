/**
 * useHealth hook tests.
 * Real useHealth and healthService; only axios mocked.
 * Fetch mocked for fallback path (getHealth) in error/fallback test.
 * Scenarios: success, error then fallback, both fail (degraded).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHealth } from './useHealth';

const mockAxiosInstance = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  interceptors: {
    request: { use: vi.fn() },
    response: { use: vi.fn() },
  },
})) as unknown as AxiosInstance;

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
  },
}));

describe('useHealth', () => {
  let queryClient: QueryClient;
  let wrapper: ({ children }: { children: ReactNode }) => ReactNode;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    vi.mocked(mockAxiosInstance.get).mockClear();
  });

  it('should return health status on success', async () => {
    const healthData = {
      status: 'healthy' as const,
      database: 'ok',
      redis: { cache: 'ok' },
    };
    vi.mocked(mockAxiosInstance.get).mockResolvedValue({
      data: healthData,
    });

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(healthData);
    expect(result.current.data?.status).toBe('healthy');
  });

  it('should fall back to fetch when apiClient.get fails and return health', async () => {
    vi.mocked(mockAxiosInstance.get).mockRejectedValue(new Error('Network error'));

    const fetchHealth = { status: 'healthy', service: 'django' };
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(fetchHealth),
    });

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(fetchHealth);
    globalThis.fetch = originalFetch;
  });

  it('should return degraded when both apiClient and fetch fail', async () => {
    vi.mocked(mockAxiosInstance.get).mockRejectedValue(new Error('Network error'));

    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Fetch failed'));

    const { result } = renderHook(() => useHealth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual({
      status: 'degraded',
      service: 'unknown',
    });
    globalThis.fetch = originalFetch;
  });
});
