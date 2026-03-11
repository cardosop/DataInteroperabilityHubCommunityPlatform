/**
 * useDataFirstAsset Hook Tests
 * Per task 29.68.6.1. Mutation structure, createDataFirst call, invalidation.
 * Uses axios mock for controlled API; real useDataFirstAsset hook.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useDataFirstAsset } from './useAssets';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  } as unknown as AxiosInstance;

  return {
    default: {
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

import { apiClient } from '../../../shared/api/client';

describe('useDataFirstAsset', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;

  function wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.post).mockClear();
  });

  it('calls POST /assets/data-first/ with file_id, key, name', async () => {
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: { asset_id: 'a1', dataset_id: 'd1', contract_id: 'c1' },
      status: 201,
    });

    const { result } = renderHook(() => useDataFirstAsset(), { wrapper });

    result.current.mutate({
      file_id: 'file-123',
      key: 'my-asset',
      name: 'My Asset',
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const postCalls = vi.mocked(mockAxiosInstance.post).mock.calls;
    const dataFirstCall = postCalls.find((c) => String(c[0]).includes('data-first'));
    expect(dataFirstCall).toBeDefined();
    expect(dataFirstCall?.[1]).toEqual({
      file_id: 'file-123',
      key: 'my-asset',
      name: 'My Asset',
    });
  });

  it('returns asset_id, dataset_id, contract_id on success', async () => {
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: { asset_id: 'a1', dataset_id: 'd1', contract_id: 'c1' },
      status: 201,
    });

    const { result } = renderHook(() => useDataFirstAsset(), { wrapper });

    let resolved: { asset_id: string; dataset_id: string | null; contract_id: string | null } | null = null;
    result.current.mutate(
      { file_id: 'f1', key: 'k1', name: 'n1' },
      {
        onSuccess: (data) => {
          resolved = data;
        },
      }
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(resolved).toEqual({ asset_id: 'a1', dataset_id: 'd1', contract_id: 'c1' });
  });

  it('accepts optional description and domain', async () => {
    vi.mocked(mockAxiosInstance.post).mockResolvedValue({
      data: { asset_id: 'a1', dataset_id: 'd1', contract_id: 'c1' },
      status: 201,
    });

    const { result } = renderHook(() => useDataFirstAsset(), { wrapper });

    result.current.mutate({
      file_id: 'f1',
      key: 'k1',
      name: 'n1',
      description: 'Test description',
      domain: 'sales',
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    const postCalls = vi.mocked(mockAxiosInstance.post).mock.calls;
    const dataFirstCall = postCalls.find((c) => String(c[0]).includes('data-first'));
    expect(dataFirstCall?.[1]).toMatchObject({
      file_id: 'f1',
      key: 'k1',
      name: 'n1',
      description: 'Test description',
      domain: 'sales',
    });
  });
});
