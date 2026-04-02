/**
 * Scheduled Ingestion Service Tests
 * Tests for scheduled ingestion service using real apiClient (no mocks of apiClient)
 *
 * Note: We mock axios at the module level to avoid real HTTP calls,
 * but we use the real apiClient instance, ensuring the service correctly
 * uses apiClient.getClient() and the actual service methods.
 */

import type { AxiosInstance } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  ScheduledIngestion,
  ScheduledIngestionCreateRequest,
  ScheduledIngestionListFilters,
  ScheduledIngestionListResponse,
  ScheduledIngestionRun,
  ScheduledIngestionTriggerRequest,
  ScheduledIngestionTriggerResponse,
  ScheduledIngestionUpdateRequest,
} from '../../../shared/types/scheduledIngestion';

// Mock axios at module level - this allows apiClient to use real methods
// but intercepts HTTP calls for testing
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
import { scheduledIngestionService } from './scheduledIngestionService';

// Get the mock instance from axios.create
vi.mocked(axios.create);

describe('scheduledIngestionService', () => {
  let mockAxiosInstance: AxiosInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    // Use the real client's methods, but we'll mock them via axios.create mock
    mockAxiosInstance = realClient;
    // Clear mock call history but keep implementations
    vi.mocked(mockAxiosInstance.get).mockClear();
    vi.mocked(mockAxiosInstance.post).mockClear();
    vi.mocked(mockAxiosInstance.patch).mockClear();
    vi.mocked(mockAxiosInstance.delete).mockClear();
  });

  describe('list', () => {
    it('should list scheduled ingestions with filters', async () => {
      const mockResponse: ScheduledIngestionListResponse = {
        count: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 'ingestion-1',
            name: 'Ingestion 1',
            status: 'active',
            schedule: '0 0 * * *',
          },
          {
            id: 'ingestion-2',
            name: 'Ingestion 2',
            status: 'paused',
            schedule: '0 12 * * *',
          },
        ] as ScheduledIngestion[],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockResponse,
      } as never);

      const filters: ScheduledIngestionListFilters = {
        page: 1,
        page_size: 20,
        status: 'active',
      };

      const result = await scheduledIngestionService.list(filters);

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'scheduled-ingestions/?page=1&page_size=20&status=active'
      );
      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
      expect(result.results[0].id).toBe('ingestion-1');
    });

    it('should list scheduled ingestions without filters', async () => {
      const mockResponse: ScheduledIngestionListResponse = {
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
        next: null,
        previous: null,
        results: [] as ScheduledIngestion[],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockResponse,
      } as never);

      const result = await scheduledIngestionService.list();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('scheduled-ingestions/');
      expect(result.count).toBe(0);
      expect(result.results).toHaveLength(0);
    });
  });

  describe('getById', () => {
    it('should get scheduled ingestion by ID', async () => {
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
      } as never);

      const result = await scheduledIngestionService.getById('ingestion-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'scheduled-ingestions/ingestion-1/'
      );
      expect(result.id).toBe('ingestion-1');
      expect(result.name).toBe('Test Ingestion');
    });
  });

  describe('create', () => {
    it('should create a new scheduled ingestion', async () => {
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
      } as never);

      const result = await scheduledIngestionService.create(createRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'scheduled-ingestions/',
        createRequest
      );
      expect(result.id).toBe('ingestion-new');
      expect(result.name).toBe('New Ingestion');
    });
  });

  describe('update', () => {
    it('should update a scheduled ingestion', async () => {
      const updateRequest: ScheduledIngestionUpdateRequest = {
        name: 'Updated Ingestion',
        schedule: '0 12 * * *',
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
      } as never);

      const result = await scheduledIngestionService.update('ingestion-1', updateRequest);

      expect(vi.mocked(mockAxiosInstance.patch)).toHaveBeenCalledWith(
        'scheduled-ingestions/ingestion-1/',
        updateRequest
      );
      expect(result.id).toBe('ingestion-1');
      expect(result.name).toBe('Updated Ingestion');
    });
  });

  describe('delete', () => {
    it('should delete a scheduled ingestion', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as never);

      await scheduledIngestionService.delete('ingestion-1');

      expect(vi.mocked(mockAxiosInstance.delete)).toHaveBeenCalledWith(
        'scheduled-ingestions/ingestion-1/'
      );
    });
  });

  describe('trigger', () => {
    it('should trigger a scheduled ingestion manually', async () => {
      const triggerRequest: ScheduledIngestionTriggerRequest = {
        force: true,
      };

      const mockTriggerResponse: ScheduledIngestionTriggerResponse = {
        run_id: 'run-123',
        status: 'queued',
        message: 'Ingestion triggered successfully',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockTriggerResponse,
      } as never);

      const result = await scheduledIngestionService.trigger('ingestion-1', triggerRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'scheduled-ingestions/ingestion-1/trigger/',
        triggerRequest,
        { timeout: 60000 }
      );
      expect(result.run_id).toBe('run-123');
      expect(result.status).toBe('queued');
    });

    it('should trigger a scheduled ingestion without request data', async () => {
      const mockTriggerResponse: ScheduledIngestionTriggerResponse = {
        run_id: 'run-456',
        status: 'queued',
        message: 'Ingestion triggered successfully',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockTriggerResponse,
      } as never);

      const result = await scheduledIngestionService.trigger('ingestion-1');

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'scheduled-ingestions/ingestion-1/trigger/',
        {},
        { timeout: 60000 }
      );
      expect(result.run_id).toBe('run-456');
    });
  });

  describe('listRuns', () => {
    it('should list runs for a scheduled ingestion', async () => {
      const mockRuns: ScheduledIngestionRun[] = [
        {
          id: 'run-1',
          ingestion_id: 'ingestion-1',
          status: 'completed',
          started_at: '2024-01-01T00:00:00Z',
          completed_at: '2024-01-01T00:05:00Z',
        },
        {
          id: 'run-2',
          ingestion_id: 'ingestion-1',
          status: 'failed',
          started_at: '2024-01-02T00:00:00Z',
          completed_at: '2024-01-02T00:02:00Z',
        },
      ];

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockRuns,
      } as never);

      const result = await scheduledIngestionService.listRuns('ingestion-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'scheduled-ingestions/ingestion-1/runs/'
      );
      expect(result).toHaveLength(2);
      expect(result[0].id).toBe('run-1');
      expect(result[1].status).toBe('failed');
    });
  });

  describe('getRunById', () => {
    it('should get run by ID', async () => {
      const mockRun: ScheduledIngestionRun = {
        id: 'run-1',
        ingestion_id: 'ingestion-1',
        status: 'completed',
        started_at: '2024-01-01T00:00:00Z',
        completed_at: '2024-01-01T00:05:00Z',
        records_processed: 1000,
        records_failed: 0,
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockRun,
      } as never);

      const result = await scheduledIngestionService.getRunById('run-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'scheduled-ingestions/runs/run-1/'
      );
      expect(result.id).toBe('run-1');
      expect(result.status).toBe('completed');
      expect(result.records_processed).toBe(1000);
    });
  });
});
