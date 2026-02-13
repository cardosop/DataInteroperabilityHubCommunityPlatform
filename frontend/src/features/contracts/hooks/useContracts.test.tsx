/**
 * Contracts Hooks Tests
 * Tests for contract hooks using real service (no mocks of service)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  Contract,
  ContractConvertRequest,
  ContractCreateRequest,
  ContractUpdateRequest,
} from '../../../shared/types/contracts';
import {
  useContract,
  useContractLineageVisualization,
  useContracts,
  useConvertContract,
  useCreateContract,
  useDeleteContract,
  useDownloadContract,
  useExportContract,
  useLintContract,
  useUpdateContract,
  useValidateContract,
} from './useContracts';

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

describe('useContracts hooks', () => {
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
    vi.mocked(mockAxiosInstance.put).mockClear();
    vi.mocked(mockAxiosInstance.delete).mockClear();
  });

  describe('useContracts', () => {
    it('should fetch contracts list', async () => {
      const mockResponse = {
        data: {
          count: 2,
          page: 1,
          page_size: 20,
          total_pages: 1,
          next: null,
          previous: null,
          results: [
            { id: 'contract-1', name: 'Contract 1' },
            { id: 'contract-2', name: 'Contract 2' },
          ] as Contract[],
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const { result } = renderHook(() => useContracts({ page: 1 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.count).toBe(2);
      expect(result.current.data?.results).toHaveLength(2);
    });
  });

  describe('useContract', () => {
    it('should fetch contract by ID when id is provided', async () => {
      const mockContract: Contract = {
        id: 'contract-1',
        name: 'Test Contract',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockContract,
      } as any);

      const { result } = renderHook(() => useContract('contract-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('contract-1');
      expect(result.current.data?.name).toBe('Test Contract');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useContract(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useCreateContract', () => {
    it('should create contract and invalidate queries', async () => {
      const createRequest: ContractCreateRequest = {
        name: 'New Contract',
        content: '{}',
        format: 'json',
      };

      const mockCreatedContract: Contract = {
        id: 'contract-new',
        name: 'New Contract',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockCreatedContract,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCreateContract(), { wrapper });

      result.current.mutate(createRequest);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('contract-new');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['contracts'] });
    });
  });

  describe('useUpdateContract', () => {
    it('should update contract and invalidate queries', async () => {
      const updateRequest: ContractUpdateRequest = {
        name: 'Updated Contract',
      };

      const mockUpdatedContract: Contract = {
        id: 'contract-1',
        name: 'Updated Contract',
        owner_email: 'owner@test.com',
        owner_name: 'Test Owner',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.put).mockResolvedValue({
        data: mockUpdatedContract,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useUpdateContract(), { wrapper });

      result.current.mutate({ id: 'contract-1', data: updateRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.name).toBe('Updated Contract');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['contracts'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['contracts', 'detail', 'contract-1'],
      });
    });
  });

  describe('useDeleteContract', () => {
    it('should delete contract and invalidate queries', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteContract(), { wrapper });

      result.current.mutate('contract-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['contracts'] });
    });
  });

  describe('useValidateContract', () => {
    it('should validate contract', async () => {
      const mockValidationResult = {
        valid: true,
        errors: [],
        warnings: [],
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockValidationResult,
      } as any);

      const { result } = renderHook(() => useValidateContract(), { wrapper });

      result.current.mutate('contract-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.valid).toBe(true);
    });
  });

  describe('useLintContract', () => {
    it('should lint contract', async () => {
      const mockLintResult = {
        issues: [
          {
            severity: 'warning',
            message: 'Unused field detected',
            path: '/fields/unused',
          },
        ],
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockLintResult,
      } as any);

      const { result } = renderHook(() => useLintContract(), { wrapper });

      result.current.mutate('contract-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.issues).toHaveLength(1);
    });
  });

  describe('useConvertContract', () => {
    it('should convert contract and invalidate queries', async () => {
      const convertRequest: ContractConvertRequest = {
        target_format: 'yaml',
      };

      const mockConvertResult = {
        content: 'name: Test Contract\n',
        format: 'yaml',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockConvertResult,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useConvertContract(), { wrapper });

      result.current.mutate({ id: 'contract-1', data: convertRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.format).toBe('yaml');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['contracts', 'detail', 'contract-1'],
      });
    });
  });

  describe('useExportContract', () => {
    it('should export contract', async () => {
      const mockBlob = new Blob(['exported content'], { type: 'application/json' });

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockBlob,
      } as any);

      const { result } = renderHook(() => useExportContract(), { wrapper });

      result.current.mutate({ id: 'contract-1', format: 'json' });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toBeInstanceOf(Blob);
    });
  });

  describe('useDownloadContract', () => {
    it('should download contract', async () => {
      const mockBlob = new Blob(['downloaded content'], { type: 'application/json' });

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockBlob,
      } as any);

      const { result } = renderHook(() => useDownloadContract(), { wrapper });

      result.current.mutate({ id: 'contract-1' });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toBeInstanceOf(Blob);
    });
  });

  describe('useContractLineageVisualization', () => {
    it('should fetch lineage visualization when contractId is provided', async () => {
      const mockLineage = {
        nodes: [
          { id: 'node-1', label: 'Asset 1', type: 'asset' },
          { id: 'node-2', label: 'Contract 1', type: 'contract' },
        ],
        links: [{ source: 'node-1', target: 'node-2', type: 'uses' }],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockLineage,
      } as any);

      const { result } = renderHook(() => useContractLineageVisualization('contract-1'), {
        wrapper,
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.nodes).toHaveLength(2);
      expect(result.current.data?.links).toHaveLength(1);
    });

    it('should not fetch when contractId is null', () => {
      const { result } = renderHook(() => useContractLineageVisualization(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });
});
