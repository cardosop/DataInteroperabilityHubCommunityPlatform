/**
 * Assets Hooks Tests
 * Tests for asset hooks using real service (no mocks of service)
 *
 * Note: We mock axios at the module level to avoid real HTTP calls,
 * but we use the real assetService instance, ensuring hooks correctly
 * use the service and React Query cache invalidation.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import React, { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  Asset,
  AssetCreateRequest,
  AssetUpdateRequest,
  AttachContractRequest,
  AttachDatasetRequest,
} from '../../../shared/types/assets';
import {
  useActivateAsset,
  useAsset,
  useAssetHealthScore,
  useAssetRecommendations,
  useAssets,
  useAttachContract,
  useAttachDataset,
  useCreateAsset,
  useDeleteAsset,
  useRecalculateHealthScore,
  useUpdateAsset,
} from './useAssets';

// Mock axios at module level
vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
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

import axios from 'axios';
import { apiClient } from '../../../shared/api/client';

const mockAxiosCreate = vi.mocked(axios.create);

describe('useAssets hooks', () => {
  let queryClient: QueryClient;
  let mockAxiosInstance: AxiosInstance;
  let wrapper: ({ children }: { children: ReactNode }) => ReactNode;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
        mutations: {
          retry: false,
        },
      },
    });

    wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.post).mockClear();
    vi.mocked(mockAxiosInstance.put).mockClear();
    vi.mocked(mockAxiosInstance.delete).mockClear();
  });

  describe('useAssets', () => {
    it('should fetch assets list', async () => {
      const mockResponse = {
        data: {
          count: 2,
          page: 1,
          page_size: 20,
          total_pages: 1,
          next: null,
          previous: null,
          results: [
            { id: 'asset-1', name: 'Asset 1' },
            { id: 'asset-2', name: 'Asset 2' },
          ] as Asset[],
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const { result } = renderHook(() => useAssets({ page: 1 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.count).toBe(2);
      expect(result.current.data?.results).toHaveLength(2);
    });

    it('should use correct query key', async () => {
      const mockResponse = {
        data: {
          count: 0,
          page: 1,
          page_size: 20,
          total_pages: 0,
          next: null,
          previous: null,
          results: [] as Asset[],
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const filters = { page: 1, search: 'test' };
      renderHook(() => useAssets(filters), { wrapper });

      await waitFor(() => {
        const queryData = queryClient.getQueryData(['assets', 'list', filters]);
        expect(queryData).toBeDefined();
      });
    });
  });

  describe('useAsset', () => {
    it('should fetch asset by ID when id is provided', async () => {
      const mockAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        status: 'active',
        visibility: 'public',
        domain: 'test-domain',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        tags: [],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockAsset,
      } as any);

      const { result } = renderHook(() => useAsset('asset-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('asset-1');
      expect(result.current.data?.name).toBe('Test Asset');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useAsset(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useCreateAsset', () => {
    it('should create asset and invalidate queries', async () => {
      const createRequest: AssetCreateRequest = {
        name: 'New Asset',
        domain: 'test-domain',
        visibility: 'public',
      };

      const mockCreatedAsset: Asset = {
        id: 'asset-new',
        name: 'New Asset',
        status: 'draft',
        visibility: 'public',
        domain: 'test-domain',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        tags: [],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockCreatedAsset,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCreateAsset(), { wrapper });

      result.current.mutate(createRequest);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('asset-new');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['assets'] });
    });
  });

  describe('useUpdateAsset', () => {
    it('should update asset and invalidate queries', async () => {
      const updateRequest: AssetUpdateRequest = {
        name: 'Updated Asset',
      };

      const mockUpdatedAsset: Asset = {
        id: 'asset-1',
        name: 'Updated Asset',
        status: 'active',
        visibility: 'public',
        domain: 'test-domain',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        tags: [],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.put).mockResolvedValue({
        data: mockUpdatedAsset,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useUpdateAsset(), { wrapper });

      result.current.mutate({ id: 'asset-1', data: updateRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.name).toBe('Updated Asset');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['assets'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['assets', 'detail', 'asset-1'],
      });
    });
  });

  describe('useDeleteAsset', () => {
    it('should delete asset and invalidate queries', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteAsset(), { wrapper });

      result.current.mutate('asset-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['assets'] });
    });
  });

  describe('useActivateAsset', () => {
    it('should activate asset and invalidate queries', async () => {
      const mockActivatedAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        status: 'active',
        visibility: 'public',
        domain: 'test-domain',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        tags: [],
        version: 2,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockActivatedAsset,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useActivateAsset(), { wrapper });

      result.current.mutate({ id: 'asset-1', version: 1 });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.status).toBe('active');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['assets'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['assets', 'detail', 'asset-1'],
      });
    });
  });

  describe('useAttachContract', () => {
    it('should attach contract and update cache', async () => {
      const attachRequest: AttachContractRequest = {
        contract_id: 'contract-1',
      };

      const mockUpdatedAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        status: 'active',
        visibility: 'public',
        domain: 'test-domain',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        tags: [],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockUpdatedAsset,
      } as any);

      const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData');
      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useAttachContract(), { wrapper });

      result.current.mutate({ id: 'asset-1', data: attachRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(setQueryDataSpy).toHaveBeenCalledWith(
        ['assets', 'detail', 'asset-1'],
        mockUpdatedAsset
      );
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['assets', 'detail', 'asset-1'],
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['assets'] });
    });
  });

  describe('useAttachDataset', () => {
    it('should attach dataset and update cache', async () => {
      const attachRequest: AttachDatasetRequest = {
        dataset_id: 'dataset-1',
      };

      const mockUpdatedAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        status: 'active',
        visibility: 'public',
        domain: 'test-domain',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        tags: [],
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockUpdatedAsset,
      } as any);

      const setQueryDataSpy = vi.spyOn(queryClient, 'setQueryData');
      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useAttachDataset(), { wrapper });

      result.current.mutate({ id: 'asset-1', data: attachRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(setQueryDataSpy).toHaveBeenCalledWith(
        ['assets', 'detail', 'asset-1'],
        mockUpdatedAsset
      );
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['assets', 'detail', 'asset-1'],
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['assets'] });
    });
  });

  describe('useAssetHealthScore', () => {
    it('should fetch health score when assetId is provided', async () => {
      const mockHealthScore = {
        score: 85,
        breakdown: {
          data_quality: 90,
          freshness: 80,
          usage: 85,
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockHealthScore,
      } as any);

      const { result } = renderHook(() => useAssetHealthScore('asset-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.score).toBe(85);
    });

    it('should not fetch when assetId is null', () => {
      const { result } = renderHook(() => useAssetHealthScore(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useRecalculateHealthScore', () => {
    it('should recalculate health score and invalidate queries', async () => {
      const mockHealthScore = {
        score: 90,
        breakdown: {
          data_quality: 95,
          freshness: 85,
          usage: 90,
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockHealthScore,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useRecalculateHealthScore(), { wrapper });

      result.current.mutate({ id: 'asset-1', breakdown: true });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.score).toBe(90);
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['assets', 'health-score', 'asset-1'],
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['assets', 'detail', 'asset-1'],
      });
    });
  });

  describe('useAssetRecommendations', () => {
    it('should fetch asset recommendations', async () => {
      const mockRecommendations = [
        {
          asset_id: 'asset-1',
          score: 0.95,
          reason: 'High usage',
        },
        {
          asset_id: 'asset-2',
          score: 0.85,
          reason: 'Similar to viewed assets',
        },
      ];

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockRecommendations,
      } as any);

      const { result } = renderHook(
        () => useAssetRecommendations({ user_id: 'user-1', limit: 10 }),
        { wrapper }
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveLength(2);
      expect(result.current.data?.[0].asset_id).toBe('asset-1');
    });
  });
});
