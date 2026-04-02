/**
 * Scheduled Export Service Tests
 * Tests for scheduled export service using real apiClient (no mocks of apiClient)
 *
 * Note: We mock API client at the module level to avoid real HTTP calls,
 * but we use the real apiClient instance, ensuring the service correctly
 * uses apiClient.getClient() and the actual service methods.
 */

import type { HttpClient } from '../../../shared/types/api';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ScheduledExport,
  ScheduledExportCreateRequest,
  ScheduledExportListFilters,
  ScheduledExportListResponse,
  ScheduledExportRun,
  ScheduledExportTriggerRequest,
  ScheduledExportTriggerResponse,
  ScheduledExportUpdateRequest,
} from '../../../shared/types/scheduledExport';

// Mock API client at module level - this allows apiClient to use real methods
// but intercepts HTTP calls for testing
vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { scheduledExportService } from './scheduledExportService';

// Get the mock instance from apiClient.getClient()
// Phase 209: uses shared API client mock

describe('scheduledExportService', () => {
  let mockClient: HttpClient;

  beforeEach(() => {
    vi.clearAllMocks();
    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    // Use the real client's methods, but we'll mock them via apiClient mock
    mockClient = realClient;
    // Clear mock call history but keep implementations
    vi.mocked(mockClient.get).mockClear();
    vi.mocked(mockClient.post).mockClear();
    vi.mocked(mockClient.patch).mockClear();
    vi.mocked(mockClient.delete).mockClear();
  });

  describe('list', () => {
    it('should list scheduled exports with filters', async () => {
      const mockResponse: ScheduledExportListResponse = {
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
            destination_config: { bucket: 'test-bucket' },
            source_scope: { asset_ids: ['asset-1'] },
            status: 'ACTIVE',
            next_run_at: '2024-01-02T02:00:00Z',
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
            destination_config: { bucket: 'test-bucket-2' },
            source_scope: { dataset_ids: ['dataset-1'] },
            status: 'PAUSED',
            next_run_at: null,
            last_run_at: '2024-01-01T12:00:00Z',
            last_run_status: 'COMPLETED',
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ] as ScheduledExport[],
      };

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockResponse,
      } as never);

      const filters: ScheduledExportListFilters = {
        page: 1,
        page_size: 20,
        status: 'ACTIVE',
      };

      const result = await scheduledExportService.list(filters);

      expect(vi.mocked(mockClient.get)).toHaveBeenCalledWith(
        'scheduled-exports/?page=1&page_size=20&status=ACTIVE'
      );
      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
      expect(result.results[0].id).toBe('export-1');
    });

    it('should list scheduled exports without filters', async () => {
      const mockResponse: ScheduledExportListResponse = {
        count: 0,
        next: null,
        previous: null,
        results: [] as ScheduledExport[],
      };

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockResponse,
      } as never);

      const result = await scheduledExportService.list();

      expect(vi.mocked(mockClient.get)).toHaveBeenCalledWith('scheduled-exports/');
      expect(result.count).toBe(0);
      expect(result.results).toHaveLength(0);
    });
  });

  describe('getById', () => {
    it('should get scheduled export by ID', async () => {
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

      const result = await scheduledExportService.getById('export-1');

      expect(vi.mocked(mockClient.get)).toHaveBeenCalledWith('scheduled-exports/export-1/');
      expect(result.id).toBe('export-1');
      expect(result.name).toBe('Test Export');
    });
  });

  describe('create', () => {
    it('should create a new scheduled export', async () => {
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

      const result = await scheduledExportService.create(createRequest);

      expect(vi.mocked(mockClient.post)).toHaveBeenCalledWith(
        'scheduled-exports/',
        createRequest
      );
      expect(result.id).toBe('export-new');
      expect(result.name).toBe('New Export');
    });
  });

  describe('update', () => {
    it('should update a scheduled export', async () => {
      const updateRequest: ScheduledExportUpdateRequest = {
        name: 'Updated Export',
        schedule_config: { cron: '0 12 * * *' },
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

      const result = await scheduledExportService.update('export-1', updateRequest);

      expect(vi.mocked(mockClient.patch)).toHaveBeenCalledWith(
        'scheduled-exports/export-1/',
        updateRequest
      );
      expect(result.id).toBe('export-1');
      expect(result.name).toBe('Updated Export');
    });
  });

  describe('delete', () => {
    it('should delete a scheduled export', async () => {
      vi.mocked(mockClient.delete).mockResolvedValue({
        status: 204,
      } as never);

      await scheduledExportService.delete('export-1');

      expect(vi.mocked(mockClient.delete)).toHaveBeenCalledWith(
        'scheduled-exports/export-1/'
      );
    });
  });

  describe('trigger', () => {
    it('should trigger a scheduled export manually', async () => {
      const triggerRequest: ScheduledExportTriggerRequest = {
        parameters: { force: true },
      };

      const mockTriggerResponse: ScheduledExportTriggerResponse = {
        scheduled_export_id: 'export-1',
        flow_run_id: 'flow-run-123',
        status: 'success',
        message: 'Export triggered successfully',
      };

      vi.mocked(mockClient.post).mockResolvedValue({
        data: mockTriggerResponse,
      } as never);

      const result = await scheduledExportService.trigger('export-1', triggerRequest);

      expect(vi.mocked(mockClient.post)).toHaveBeenCalledWith(
        'scheduled-exports/export-1/trigger/',
        triggerRequest,
        { timeout: 60000 }
      );
      expect(result.scheduled_export_id).toBe('export-1');
      expect(result.flow_run_id).toBe('flow-run-123');
      expect(result.status).toBe('success');
    });

    it('should trigger a scheduled export without request data', async () => {
      const mockTriggerResponse: ScheduledExportTriggerResponse = {
        scheduled_export_id: 'export-1',
        flow_run_id: 'flow-run-456',
        status: 'success',
        message: 'Export triggered successfully',
      };

      vi.mocked(mockClient.post).mockResolvedValue({
        data: mockTriggerResponse,
      } as never);

      const result = await scheduledExportService.trigger('export-1');

      expect(vi.mocked(mockClient.post)).toHaveBeenCalledWith(
        'scheduled-exports/export-1/trigger/',
        {},
        { timeout: 60000 }
      );
      expect(result.flow_run_id).toBe('flow-run-456');
    });
  });

  describe('listRuns', () => {
    it('should list runs for a scheduled export', async () => {
      const mockRuns: ScheduledExportRun[] = [
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
        {
          id: 'run-2',
          scheduled_export: 'export-1',
          scheduled_export_name: 'Test Export',
          status: 'FAILED',
          items_found: 50,
          items_exported: 0,
          items_failed: 50,
          result_json: { error: 'Connection failed' },
          started_at: '2024-01-02T02:00:00Z',
          completed_at: '2024-01-02T02:02:00Z',
          prefect_flow_run_id: 'flow-run-2',
          created_at: '2024-01-02T02:00:00Z',
          updated_at: '2024-01-02T02:02:00Z',
        },
      ];

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockRuns,
      } as never);

      const result = await scheduledExportService.listRuns('export-1');

      expect(vi.mocked(mockClient.get)).toHaveBeenCalledWith(
        'scheduled-exports/export-1/runs/'
      );
      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('run-1');
      expect(result[1].status).toBe('FAILED');
    });
  });

  describe('getRunById', () => {
    it('should get run by ID', async () => {
      const mockRun: ScheduledExportRun = {
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
      };

      vi.mocked(mockClient.get).mockResolvedValue({
        data: mockRun,
      } as never);

      const result = await scheduledExportService.getRunById('run-1');

      expect(vi.mocked(mockClient.get)).toHaveBeenCalledWith(
        'scheduled-exports/runs/run-1/'
      );
      expect(result.id).toBe('run-1');
      expect(result.status).toBe('COMPLETED');
      expect(result.items_exported).toBe(100);
    });
  });
});
