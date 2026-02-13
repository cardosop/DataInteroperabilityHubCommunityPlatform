/**
 * Contract Service Tests
 * Tests for contract service using real apiClient (no mocks of apiClient)
 *
 * Note: We mock axios at the module level to avoid real HTTP calls,
 * but we use the real apiClient instance, ensuring the service correctly
 * uses apiClient.getClient() and the actual service methods.
 */

import type { AxiosInstance } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  Contract,
  ContractCreateRequest,
  ContractUpdateRequest,
  ContractListFilters,
  ContractValidationResult,
  ContractLintResult,
  ContractConvertRequest,
  ContractConvertResult,
} from '../../../shared/types/contracts';
import type {
  ContractLineageVisualization,
  ContractLineageVisualizationParams,
} from '../../../shared/types/lineage';

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
import { contractService } from './contractService';

// Get the mock instance from axios.create
const mockAxiosCreate = vi.mocked(axios.create);

describe('contractService', () => {
  let mockAxiosInstance: AxiosInstance;

  beforeEach(() => {
    vi.clearAllMocks();
    // Get the real client instance from apiClient
    const realClient = apiClient.getClient();
    // Use the real client's methods, but we'll mock them via axios.create mock
    mockAxiosInstance = realClient;
  });

  describe('list', () => {
    it('should list contracts with filters', async () => {
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
              id: 'contract-1',
              name: 'Contract 1',
              owner_email: 'owner1@test.com',
            },
            {
              id: 'contract-2',
              name: 'Contract 2',
              owner_email: 'owner2@test.com',
            },
          ] as Contract[],
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const filters: ContractListFilters = {
        page: 1,
        page_size: 20,
        search: 'test',
        owner_email: 'owner@test.com',
        asset_id: 'asset-1',
      };

      const result = await contractService.list(filters);

      // URLSearchParams encodes special characters, so check that all params are present
      const callArgs = vi.mocked(mockAxiosInstance.get).mock.calls[0][0];
      expect(callArgs).toContain('contracts/');
      expect(callArgs).toContain('page=1');
      expect(callArgs).toContain('page_size=20');
      expect(callArgs).toContain('search=test');
      expect(callArgs).toContain('owner_email=owner%40test.com'); // @ is encoded as %40
      expect(callArgs).toContain('asset_id=asset-1');
      expect(result.count).toBe(2);
      expect(result.results).toHaveLength(2);
      expect(result.results[0].id).toBe('contract-1');
    });

    it('should list contracts without filters', async () => {
      const mockResponse = {
        data: {
          count: 0,
          page: 1,
          page_size: 20,
          total_pages: 0,
          next: null,
          previous: null,
          results: [] as Contract[],
        },
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue(mockResponse as any);

      const result = await contractService.list();

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('contracts/');
      expect(result.count).toBe(0);
      expect(result.results).toHaveLength(0);
    });
  });

  describe('getById', () => {
    it('should get contract by ID', async () => {
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

      const result = await contractService.getById('contract-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('contracts/contract-1/');
      expect(result.id).toBe('contract-1');
      expect(result.name).toBe('Test Contract');
    });
  });

  describe('create', () => {
    it('should create a new contract', async () => {
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

      const result = await contractService.create(createRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('contracts/', createRequest);
      expect(result.id).toBe('contract-new');
      expect(result.name).toBe('New Contract');
    });
  });

  describe('update', () => {
    it('should update a contract', async () => {
      const updateRequest: ContractUpdateRequest = {
        name: 'Updated Contract',
        content: '{"updated": true}',
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

      const result = await contractService.update('contract-1', updateRequest);

      expect(vi.mocked(mockAxiosInstance.put)).toHaveBeenCalledWith('contracts/contract-1/', updateRequest);
      expect(result.id).toBe('contract-1');
      expect(result.name).toBe('Updated Contract');
    });
  });

  describe('delete', () => {
    it('should delete a contract', async () => {
      vi.mocked(mockAxiosInstance.delete).mockResolvedValue({
        status: 204,
      } as any);

      await contractService.delete('contract-1');

      expect(vi.mocked(mockAxiosInstance.delete)).toHaveBeenCalledWith('contracts/contract-1/');
    });
  });

  describe('validate', () => {
    it('should validate a contract', async () => {
      const mockValidationResult: ContractValidationResult = {
        valid: true,
        errors: [],
        warnings: [],
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockValidationResult,
      } as any);

      const result = await contractService.validate('contract-1');

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('contracts/contract-1/validate/');
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should return validation errors when contract is invalid', async () => {
      const mockValidationResult: ContractValidationResult = {
        valid: false,
        errors: ['Invalid schema', 'Missing required field'],
        warnings: ['Deprecated field used'],
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockValidationResult,
      } as any);

      const result = await contractService.validate('contract-1');

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(2);
      expect(result.warnings).toHaveLength(1);
    });
  });

  describe('lint', () => {
    it('should lint a contract', async () => {
      const mockLintResult: ContractLintResult = {
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

      const result = await contractService.lint('contract-1');

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith('contracts/contract-1/lint/');
      expect(result.issues).toHaveLength(1);
      expect(result.issues[0].severity).toBe('warning');
    });
  });

  describe('convert', () => {
    it('should convert a contract format', async () => {
      const convertRequest: ContractConvertRequest = {
        target_format: 'yaml',
      };

      const mockConvertResult: ContractConvertResult = {
        content: 'name: Test Contract\n',
        format: 'yaml',
      };

      vi.mocked(mockAxiosInstance.post).mockResolvedValue({
        data: mockConvertResult,
      } as any);

      const result = await contractService.convert('contract-1', convertRequest);

      expect(vi.mocked(mockAxiosInstance.post)).toHaveBeenCalledWith(
        'contracts/contract-1/convert/',
        convertRequest
      );
      expect(result.format).toBe('yaml');
      expect(result.content).toBe('name: Test Contract\n');
    });
  });

  describe('export', () => {
    it('should export a contract', async () => {
      const mockBlob = new Blob(['exported content'], { type: 'application/json' });

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockBlob,
      } as any);

      const result = await contractService.export('contract-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('contracts/contract-1/export/', {
        responseType: 'blob',
      });
      expect(result).toBeInstanceOf(Blob);
    });

    it('should export a contract with format', async () => {
      const mockBlob = new Blob(['exported content'], { type: 'application/yaml' });

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockBlob,
      } as any);

      const result = await contractService.export('contract-1', 'yaml');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('contracts/contract-1/export/?format=yaml', {
        responseType: 'blob',
      });
      expect(result).toBeInstanceOf(Blob);
    });
  });

  describe('download', () => {
    it('should download a contract', async () => {
      const mockBlob = new Blob(['downloaded content'], { type: 'application/json' });

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockBlob,
      } as any);

      const result = await contractService.download('contract-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('contracts/contract-1/download/', {
        responseType: 'blob',
      });
      expect(result).toBeInstanceOf(Blob);
    });

    it('should download a contract with format', async () => {
      const mockBlob = new Blob(['downloaded content'], { type: 'application/yaml' });

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockBlob,
      } as any);

      const result = await contractService.download('contract-1', 'yaml');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith('contracts/contract-1/download/?format=yaml', {
        responseType: 'blob',
      });
      expect(result).toBeInstanceOf(Blob);
    });
  });

  describe('getLineageVisualization', () => {
    it('should get contract lineage visualization', async () => {
      const mockLineage: ContractLineageVisualization = {
        nodes: [
          { id: 'node-1', label: 'Asset 1', type: 'asset' },
          { id: 'node-2', label: 'Contract 1', type: 'contract' },
        ],
        links: [{ source: 'node-1', target: 'node-2', type: 'uses' }],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockLineage,
      } as any);

      const params: ContractLineageVisualizationParams = {
        format: 'json',
        max_depth: 3,
      };

      const result = await contractService.getLineageVisualization('contract-1', params);

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'contracts/contract-1/lineage/visualization/?format=json&max_depth=3'
      );
      expect(result.nodes).toHaveLength(2);
      expect(result.links).toHaveLength(1);
    });

    it('should get contract lineage visualization with default params', async () => {
      const mockLineage: ContractLineageVisualization = {
        nodes: [],
        links: [],
      };

      vi.mocked(mockAxiosInstance.get).mockResolvedValue({
        data: mockLineage,
      } as any);

      const result = await contractService.getLineageVisualization('contract-1');

      expect(vi.mocked(mockAxiosInstance.get)).toHaveBeenCalledWith(
        'contracts/contract-1/lineage/visualization/?format=json'
      );
      expect(result.nodes).toHaveLength(0);
    });
  });
});
