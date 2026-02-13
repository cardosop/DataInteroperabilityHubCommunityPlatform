/**
 * Asset Service Tests
 * Tests for asset service using real apiClient (no mocks of apiClient)
 *
 * Note: We mock axios at the module level to avoid real HTTP calls,
 * but we use the real apiClient instance, ensuring the service correctly
 * uses apiClient.getClient() and the actual service methods.
 */

import type { AxiosInstance } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  Asset,
  AssetCreateRequest,
  AssetHealthScoreResponse,
  AssetListFilters,
  AssetRecommendation,
  AssetRecommendationsFilters,
  AssetUpdateRequest,
  AttachContractRequest,
  AttachDatasetRequest,
} from '../../../shared/types/assets';

// Mock axios at module level - this allows apiClient to use real methods
// but intercepts HTTP calls for testing
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
import { assetService } from './assetService';

// Get the mock instance from axios.create
const mockAxiosCreate = vi.mocked(axios.create);

describe('assetService', () => {
  let mockAxiosInstance: AxiosInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    // Use the real client's methods, but we'll mock them via axios.create mock
    mockAxiosInstance = realClient;
  });

  describe('list', () => {
    it('should list assets with filters', async () => {
      const mockResponse = {
        data: {
          count: 2,
          page: 1,
          page_size: 20,
          total_pages: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'asset-1',
              name: 'Asset 1',
              status: 'active',
              visibility: 'public',
            },
            {
              id: 'asset-2',
              name: 'Asset 2',
              status: 'draft',
              visibility: 'private',
            },
          ] as Asset[],
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const filters: AssetListFilters = {
        page: 1,
        page_size: 20,
        search: 'test',
        status: 'active',
        visibility: 'public',
      };

      const result = await assetService.list(filters);

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'assets/?page=1&page_size=20&search=test&status=active&visibility=public'
      );
      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
      expect(result.results[0].id).toBe('asset-1');
    });

    it('should list assets without filters', async () => {
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

      const result = await assetService.list();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('assets/');
      expect(result.count).toBe(0);
      expect(result.results).toHaveLength(0);
    });
  });

  describe('getById', () => {
    it('should throw when asset not found (404)', async () => {
      const err: any = new Error('Not Found');
      err.response = {
        status: 404,
        data: { error: { code: 'NOT_FOUND', message: 'Asset not found' } },
      };
      vi.mocked(mockAxiosInstance.get).mockRejectedValue(err);

      await expect(assetService.getById('nonexistent')).rejects.toThrow();
    });

    it('should get asset by ID', async () => {
      const mockAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        description: 'Test description',
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

      const result = await assetService.getById('asset-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('assets/asset-1/');
      expect(result.id).toBe('asset-1');
      expect(result.name).toBe('Test Asset');
    });
  });

  describe('create', () => {
    it('should create a new asset', async () => {
      const createRequest: AssetCreateRequest = {
        name: 'New Asset',
        description: 'New description',
        domain: 'test-domain',
        visibility: 'public',
      };

      const mockCreatedAsset: Asset = {
        id: 'asset-new',
        name: 'New Asset',
        description: 'New description',
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

      const result = await assetService.create(createRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('assets/', createRequest);
      expect(result.id).toBe('asset-new');
      expect(result.name).toBe('New Asset');
    });
  });

  describe('update', () => {
    it('should update an asset', async () => {
      const updateRequest: AssetUpdateRequest = {
        name: 'Updated Asset',
        description: 'Updated description',
      };

      const mockUpdatedAsset: Asset = {
        id: 'asset-1',
        name: 'Updated Asset',
        description: 'Updated description',
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

      const result = await assetService.update('asset-1', updateRequest);

      expect(vi.mocked(mockAxiosInstance.put)).toHaveBeenCalledWith(
        'assets/asset-1/',
        updateRequest
      );
      expect(result.id).toBe('asset-1');
      expect(result.name).toBe('Updated Asset');
    });
  });

  describe('delete', () => {
    it('should delete an asset', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      await assetService.delete('asset-1');

      expect(vi.mocked(mockAxiosInstance.delete)).toHaveBeenCalledWith('assets/asset-1/');
    });
  });

  describe('activate', () => {
    it('should activate an asset', async () => {
      const mockActivatedAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        description: 'Test description',
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

      const result = await assetService.activate('asset-1', 1);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('assets/asset-1/activate/', {
        version: 1,
      });
      expect(result.id).toBe('asset-1');
      expect(result.status).toBe('active');
    });
  });

  describe('attachContract', () => {
    it('should attach a contract to an asset', async () => {
      const attachRequest: AttachContractRequest = {
        contract_id: 'contract-1',
      };

      const mockAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        description: 'Test description',
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
        data: mockAsset,
      } as any);

      const result = await assetService.attachContract('asset-1', attachRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'assets/asset-1/contracts/',
        attachRequest
      );
      expect(result.id).toBe('asset-1');
    });
  });

  describe('attachDataset', () => {
    it('should attach a dataset to an asset', async () => {
      const attachRequest: AttachDatasetRequest = {
        dataset_id: 'dataset-1',
      };

      const mockAsset: Asset = {
        id: 'asset-1',
        name: 'Test Asset',
        description: 'Test description',
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
        data: mockAsset,
      } as any);

      const result = await assetService.attachDataset('asset-1', attachRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'assets/asset-1/datasets/',
        attachRequest
      );
      expect(result.id).toBe('asset-1');
    });
  });

  describe('getHealthScore', () => {
    it('should get asset health score', async () => {
      const mockHealthScore: AssetHealthScoreResponse = {
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

      const result = await assetService.getHealthScore('asset-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('assets/asset-1/health-score/');
      expect(result.score).toBe(85);
    });

    it('should get asset health score with options', async () => {
      const mockHealthScore: AssetHealthScoreResponse = {
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

      const result = await assetService.getHealthScore('asset-1', {
        recalculate: true,
        breakdown: true,
      });

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'assets/asset-1/health-score/?recalculate=true&breakdown=true'
      );
      expect(result.score).toBe(85);
    });
  });

  describe('getRecommendations', () => {
    it('should get asset recommendations', async () => {
      const mockRecommendations: AssetRecommendation[] = [
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

      const filters: AssetRecommendationsFilters = {
        user_id: 'user-1',
        limit: 10,
      };

      const result = await assetService.getRecommendations(filters);

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'assets/recommendations/?user_id=user-1&limit=10'
      );
      expect(result).toHaveLength(2);
      expect(result[0].asset_id).toBe('asset-1');
    });

    it('should get asset recommendations without filters', async () => {
      const mockRecommendations: AssetRecommendation[] = [];

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockRecommendations,
      } as any);

      const result = await assetService.getRecommendations();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('assets/recommendations/');
      expect(result).toHaveLength(0);
    });
  });
});
