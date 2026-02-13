/**
 * Scheduled Ingestion Hooks Tests
 * Tests for scheduled ingestion hooks using real service (no mocks of service)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { AxiosInstance } from 'axios';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ScheduledIngestion,
  ScheduledIngestionCreateRequest,
  ScheduledIngestionTriggerRequest,
  ScheduledIngestionUpdateRequest,
} from '../../../shared/types/scheduledIngestion';
import {
  useCreateScheduledIngestion,
  useDeleteScheduledIngestion,
  useScheduledIngestion,
  useScheduledIngestionRuns,
  useScheduledIngestions,
  useTriggerScheduledIngestion,
  useUpdateScheduledIngestion,
} from './useScheduledIngestion';

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

describe('useScheduledIngestion hooks', () => {
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

  describe('useScheduledIngestions', () => {
    it('should fetch scheduled ingestions list', async () => {
      const mockResponse = {
        count: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          { id: 'ingestion-1', name: 'Ingestion 1', status: 'active' },
          { id: 'ingestion-2', name: 'Ingestion 2', status: 'paused' },
        ] as ScheduledIngestion[],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockResponse,
      } as any);

      const { result } = renderHook(() => useScheduledIngestions({ page: 1 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.count).toBe(2);
      expect(result.current.data?.results).toHaveLength(2);
    });
  });

  describe('useScheduledIngestion', () => {
    it('should fetch scheduled ingestion by ID when id is provided', async () => {
      const mockIngestion: ScheduledIngestion = {
        id: 'ingestion-1',
        name: 'Test Ingestion',
        status: 'active',
        schedule: '0 0 * * *',
        source_type: 'api',
        source_config: {},
        destination_type: 'dataset',
        destination_config: {},
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockIngestion,
      } as any);

      const { result } = renderHook(() => useScheduledIngestion('ingestion-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('ingestion-1');
      expect(result.current.data?.name).toBe('Test Ingestion');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useScheduledIngestion(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useScheduledIngestionRuns', () => {
    it('should fetch runs when id is provided', async () => {
      const mockRuns = [
        {
          id: 'run-1',
          ingestion_id: 'ingestion-1',
          status: 'completed',
          started_at: '2024-01-01T00:00:00Z',
          completed_at: '2024-01-01T00:05:00Z',
        },
      ];

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockRuns,
      } as any);

      const { result } = renderHook(() => useScheduledIngestionRuns('ingestion-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveLength(1);
      expect(result.current.data?.[0].id).toBe('run-1');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useScheduledIngestionRuns(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useCreateScheduledIngestion', () => {
    it('should create scheduled ingestion and invalidate queries', async () => {
      const createRequest: ScheduledIngestionCreateRequest = {
        name: 'New Ingestion',
        schedule: '0 0 * * *',
        source_type: 'api',
        source_config: {},
        destination_type: 'dataset',
        destination_config: {},
      };

      const mockCreatedIngestion: ScheduledIngestion = {
        id: 'ingestion-new',
        name: 'New Ingestion',
        status: 'active',
        schedule: '0 0 * * *',
        source_type: 'api',
        source_config: {},
        destination_type: 'dataset',
        destination_config: {},
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockCreatedIngestion,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCreateScheduledIngestion(), { wrapper });

      result.current.mutate(createRequest);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('ingestion-new');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-ingestions'] });
    });
  });

  describe('useUpdateScheduledIngestion', () => {
    it('should update scheduled ingestion and invalidate queries', async () => {
      const updateRequest: ScheduledIngestionUpdateRequest = {
        name: 'Updated Ingestion',
      };

      const mockUpdatedIngestion: ScheduledIngestion = {
        id: 'ingestion-1',
        name: 'Updated Ingestion',
        status: 'active',
        schedule: '0 12 * * *',
        source_type: 'api',
        source_config: {},
        destination_type: 'dataset',
        destination_config: {},
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockAxiosInstance.patch).mockResolvedValue({
        data: mockUpdatedIngestion,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useUpdateScheduledIngestion(), { wrapper });

      result.current.mutate({ id: 'ingestion-1', data: updateRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.name).toBe('Updated Ingestion');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-ingestions'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['scheduled-ingestions', 'detail', 'ingestion-1'],
      });
    });
  });

  describe('useDeleteScheduledIngestion', () => {
    it('should delete scheduled ingestion and invalidate queries', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteScheduledIngestion(), { wrapper });

      result.current.mutate('ingestion-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-ingestions'] });
    });
  });

  describe('useTriggerScheduledIngestion', () => {
    it('should trigger scheduled ingestion and invalidate queries', async () => {
      const triggerRequest: ScheduledIngestionTriggerRequest = {
        force: true,
      };

      const mockTriggerResponse = {
        run_id: 'run-123',
        status: 'queued',
        message: 'Ingestion triggered successfully',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockTriggerResponse,
      } as any);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useTriggerScheduledIngestion(), { wrapper });

      result.current.mutate({ id: 'ingestion-1', data: triggerRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.run_id).toBe('run-123');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-ingestions'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['scheduled-ingestions', 'detail', 'ingestion-1'],
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['scheduled-ingestions', 'runs', 'ingestion-1'],
      });
    });
  });
});
