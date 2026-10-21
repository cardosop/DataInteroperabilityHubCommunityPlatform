/**
 * Scheduled Export Hooks Tests
 * Tests for scheduled export hooks using real service (no mocks of service)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { HttpClient } from '../../../shared/types/api';
import { type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ScheduledExport,
  ScheduledExportCreateRequest,
  ScheduledExportTriggerRequest,
  ScheduledExportUpdateRequest,
} from '../../../shared/types/scheduledExport';
import {
  useCreateScheduledExport,
  useDeleteScheduledExport,
  useScheduledExport,
  useScheduledExportRuns,
  useScheduledExports,
  useTriggerScheduledExport,
  useUpdateScheduledExport,
} from './useScheduledExport';

// Mock API client at module level
vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';

// Phase 209: uses shared API client mock

describe('useScheduledExport hooks', () => {
  let queryClient: QueryClient;
  let mockClient: HttpClient;
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
    mockClient = realClient;
    vi.mocked(mockClient.get).mockClear();
    vi.mocked(mockClient.post).mockClear();
    vi.mocked(mockClient.patch).mockClear();
    vi.mocked(mockClient.delete).mockClear();
  });

  describe('useScheduledExports', () => {
    it('should fetch scheduled exports list', async () => {
      const mockResponse = {
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 'export-1',
            tenant: 'tenant-1',
            tenant_name: 'Test Tenant',
            name: 'Export 1',
            schedule_config: { cron: '0 2 * * *' },
            destination_type: 'S3',
            destination_config: {},
            source_scope: {},
            status: 'ACTIVE',
            next_run_at: null,
            last_run_at: null,
            last_run_status: null,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
          {
            id: 'export-2',
            tenant: 'tenant-1',
            tenant_name: 'Test Tenant',
            name: 'Export 2',
            schedule_config: { cron: '0 12 * * *' },
            destination_type: 'GCS',
            destination_config: {},
            source_scope: {},
            status: 'PAUSED',
            next_run_at: null,
            last_run_at: null,
            last_run_status: null,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ] as ScheduledExport[],
      };

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockResponse,
      } as never);

      const { result } = renderHook(() => useScheduledExports({ page: 1 }), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.count).toBe(2);
      expect(result.current.data?.results).toHaveLength(2);
    });
  });

  describe('useScheduledExport', () => {
    it('should fetch scheduled export by ID when id is provided', async () => {
      const mockExport: ScheduledExport = {
        id: 'export-1',
        tenant: 'tenant-1',
        tenant_name: 'Test Tenant',
        name: 'Test Export',
        schedule_config: { cron: '0 2 * * *', timezone: 'UTC' },
        destination_type: 'S3',
        destination_config: { bucket: 'test-bucket' },
        source_scope: { asset_ids: ['asset-1'] },
        status: 'ACTIVE',
        next_run_at: '2024-01-02T02:00:00Z',
        last_run_at: null,
        last_run_status: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockExport,
      } as never);

      const { result } = renderHook(() => useScheduledExport('export-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('export-1');
      expect(result.current.data?.name).toBe('Test Export');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useScheduledExport(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useScheduledExportRuns', () => {
    it('should fetch runs when id is provided', async () => {
      const mockRuns = [
        {
          id: 'run-1',
          scheduled_export: 'export-1',
          scheduled_export_name: 'Test Export',
          status: 'COMPLETED',
          items_found: 100,
          items_exported: 100,
          items_failed: 0,
          result_json: null,
          started_at: '2024-01-01T02:00:00Z',
          completed_at: '2024-01-01T02:05:00Z',
          prefect_flow_run_id: 'flow-run-1',
          created_at: '2024-01-01T02:00:00Z',
          updated_at: '2024-01-01T02:05:00Z',
        },
      ];

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockRuns,
      } as never);

      const { result } = renderHook(() => useScheduledExportRuns('export-1'), { wrapper });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveLength(1);
      expect(result.current.data?.[0].id).toBe('run-1');
    });

    it('should not fetch when id is null', () => {
      const { result } = renderHook(() => useScheduledExportRuns(null), { wrapper });

      expect(result.current.isFetching).toBe(false);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('useCreateScheduledExport', () => {
    it('should create scheduled export and invalidate queries', async () => {
      const createRequest: ScheduledExportCreateRequest = {
        name: 'New Export',
        schedule_config: { cron: '0 2 * * *' },
        destination_type: 'S3',
        destination_config: { bucket: 'test-bucket' },
        source_scope: { asset_ids: ['asset-1'] },
      };

      const mockCreatedExport: ScheduledExport = {
        id: 'export-new',
        tenant: 'tenant-1',
        tenant_name: 'Test Tenant',
        name: 'New Export',
        schedule_config: { cron: '0 2 * * *' },
        destination_type: 'S3',
        destination_config: { bucket: 'test-bucket' },
        source_scope: { asset_ids: ['asset-1'] },
        status: 'ACTIVE',
        next_run_at: '2024-01-02T02:00:00Z',
        last_run_at: null,
        last_run_status: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      vi.mocked(mockClient.post).mockResolvedValue({
        data: mockCreatedExport,
      } as never);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCreateScheduledExport(), { wrapper });

      result.current.mutate(createRequest);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.id).toBe('export-new');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-exports'] });
    });
  });

  describe('useUpdateScheduledExport', () => {
    it('should update scheduled export and invalidate queries', async () => {
      const updateRequest: ScheduledExportUpdateRequest = {
        name: 'Updated Export',
      };

      const mockUpdatedExport: ScheduledExport = {
        id: 'export-1',
        tenant: 'tenant-1',
        tenant_name: 'Test Tenant',
        name: 'Updated Export',
        schedule_config: { cron: '0 12 * * *' },
        destination_type: 'S3',
        destination_config: { bucket: 'test-bucket' },
        source_scope: { asset_ids: ['asset-1'] },
        status: 'ACTIVE',
        next_run_at: '2024-01-02T12:00:00Z',
        last_run_at: null,
        last_run_status: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
      };

      vi.mocked(mockClient.patch).mockResolvedValue({
        data: mockUpdatedExport,
      } as never);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useUpdateScheduledExport(), { wrapper });

      result.current.mutate({ id: 'export-1', data: updateRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.name).toBe('Updated Export');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-exports'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['scheduled-exports', 'detail', 'export-1'],
      });
    });
  });

  describe('useDeleteScheduledExport', () => {
    it('should delete scheduled export and invalidate queries', async () => {
      vi.mocked(mockClient.delete).mockResolvedValue({
        status: 204,
      } as never);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useDeleteScheduledExport(), { wrapper });

      result.current.mutate('export-1');

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-exports'] });
    });
  });

  describe('useTriggerScheduledExport', () => {
    it('should trigger scheduled export and invalidate queries', async () => {
      const triggerRequest: ScheduledExportTriggerRequest = {
        parameters: { force: true },
      };

      const mockTriggerResponse = {
        scheduled_export_id: 'export-1',
        flow_run_id: 'flow-run-123',
        status: 'success',
        message: 'Export triggered successfully',
      };

      vi.mocked(mockClient.post).mockResolvedValue({
        data: mockTriggerResponse,
      } as never);

      const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useTriggerScheduledExport(), { wrapper });

      result.current.mutate({ id: 'export-1', data: triggerRequest });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data?.flow_run_id).toBe('flow-run-123');
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({ queryKey: ['scheduled-exports'] });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['scheduled-exports', 'detail', 'export-1'],
      });
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['scheduled-exports', 'runs', 'export-1'],
      });
    });
  });
});
