/**
 * Governance Retention Hooks Tests
 * Tests for retention hooks using real service (no mocks of service)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  RetentionPolicy,
  RetentionPolicyCreateRequest,
  RetentionPolicyUpdateRequest,
} from '../../../shared/types/governanceRetention';
import {
  useCreateRetentionPolicy,
  useDeleteRetentionPolicy,
  useRetentionPolicies,
  useRetentionPolicy,
  useUpdateRetentionPolicy,
} from './useRetention';

// Mock axios at module level
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

import axios from 'axios';
import { apiClient } from '../../../shared/api/client';

const mockAxiosCreate = vi.mocked(axios.create);

describe('useRetention hooks', () => {
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

    const realClient = apiClient.getClient();
    mockAxiosInstance = realClient;
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.post).mockClear();
    vi.mocked(mockAxiosInstance.patch).mockClear();
    vi.mocked(mockAxiosInstance.delete).mockClear();
  });

  describe('useRetentionPolicies', () => {
    it('should fetch retention policies list', async () => {
      const mockResponse = {
        count: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          { id: 'policy-1', name: 'Policy 1', enabled: true },
          { id: 'policy-2', name: 'Policy 2', enabled: false },
        ] as RetentionPolicy[],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockResponse,
      } as any);

      const { result } = renderHook(() => useRetentionPolicies({ page: 1 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.count).toBe(2);
      expect(result.current.data?.results).toHaveLength(2);
    });
  });

  describe('useRetentionPolicy', () => {
    it('should fetch retention policy by ID when id is provided', async () => {
      const mockPolicy: RetentionPolicy = {
        id: 'policy-1',
        tenant: 'tenant-1',
        name: 'Test Policy',
        description: 'Test description',
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: 'TIME_BASED',
        retention_period_days: 30,
        event_trigger: null,
        action: 'SOFT_DELETE',
        grace_period_days: 7,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockPolicy,
      } as any);

      const { result } = renderHook(() => useRetentionPolicy('policy-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('policy-1');
      expect(result.current.data?.name).toBe('Test Policy');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useRetentionPolicy(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useCreateRetentionPolicy', () => {
    it('should create retention policy and invalidate queries', async () => {
      const createRequest: RetentionPolicyCreateRequest = {
        name: 'New Policy',
        asset: 'asset-1',
        policy_type: 'TIME_BASED',
        retention_period_days: 30,
        action: 'SOFT_DELETE',
      };

      const mockCreatedPolicy: RetentionPolicy = {
        id: 'policy-new',
        tenant: 'tenant-1',
        name: 'New Policy',
        description: null,
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: 'TIME_BASED',
        retention_period_days: 30,
        event_trigger: null,
        action: 'SOFT_DELETE',
        grace_period_days: 7,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockCreatedPolicy,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCreateRetentionPolicy(), { wrapper });

      result.current.mutate(createRequest);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('policy-new');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['governance', 'retention-policies'],
      });
    });
  });

  describe('useUpdateRetentionPolicy', () => {
    it('should update retention policy and invalidate queries', async () => {
      const updateRequest: RetentionPolicyUpdateRequest = {
        id: 'policy-1',
        name: 'Updated Policy',
        retention_period_days: 60,
      };

      const mockUpdatedPolicy: RetentionPolicy = {
        id: 'policy-1',
        tenant: 'tenant-1',
        name: 'Updated Policy',
        description: 'Test description',
        asset: 'asset-1',
        dataset: null,
        file: null,
        policy_type: 'TIME_BASED',
        retention_period_days: 60,
        event_trigger: null,
        action: 'SOFT_DELETE',
        grace_period_days: 7,
        legal_hold: false,
        legal_hold_reason: null,
        legal_hold_expires_at: null,
        enabled: true,
        last_enforced_at: null,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.patch).mockResolvedValue({
        data: mockUpdatedPolicy,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useUpdateRetentionPolicy(), { wrapper });

      result.current.mutate(updateRequest);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.name).toBe('Updated Policy');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['governance', 'retention-policies'],
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['governance', 'retention-policies', 'detail', 'policy-1'],
      });
    });
  });

  describe('useDeleteRetentionPolicy', () => {
    it('should delete retention policy and invalidate queries', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteRetentionPolicy(), { wrapper });

      result.current.mutate('policy-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['governance', 'retention-policies'],
      });
    });
  });
});
