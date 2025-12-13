/**
 * Contracts API Tests
 * 
 * Comprehensive tests for all ContractsAPI methods.
 */

import { DataHubClient } from '../client';
import { ContractsAPI } from '../contracts';
import { ValidationError, NotFoundError } from '../errors';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('ContractsAPI', () => {
  let client: DataHubClient;
  let contractsAPI: ContractsAPI;
  const mockAxiosInstance = {
    request: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset mock implementation to default (resolves with empty response)
    mockAxiosInstance.request.mockReset();
    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
    
    client = new DataHubClient({
      baseUrl: 'https://api.example.com/api/v1',
      apiToken: 'test-token',
    });
    
    contractsAPI = new ContractsAPI(client);
  });

  describe('list', () => {
    it('should list contracts with default parameters', async () => {
      const expectedResponse = {
        count: 100,
        page: 1,
        page_size: 50,
        results: [{ id: '123', status: 'ACTIVE' }],
      };

      // Mock axios request to return response directly (interceptors handle it)
      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const result = await contractsAPI.list();

      expect(result).toEqual(expectedResponse);
      // Verify the request was made (the actual call goes through client.get which uses client.request)
      expect(mockAxiosInstance.request).toHaveBeenCalled();
      const callArgs = mockAxiosInstance.request.mock.calls[0][0];
      expect(callArgs.method).toBe('GET');
      expect(callArgs.url).toBe('contracts/');
      expect(callArgs.params).toEqual({ page: 1, page_size: 50 });
    });

    it('should list contracts with pagination', async () => {
      const expectedResponse = {
        count: 200,
        page: 2,
        page_size: 25,
        results: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await contractsAPI.list({ page: 2, pageSize: 25 });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/',
          params: { page: 2, page_size: 25 },
        })
      );
    });

    it('should list contracts with filters', async () => {
      const expectedResponse = {
        count: 10,
        results: [{ id: '123', owner_email: 'test@example.com' }],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await contractsAPI.list({
        ownerEmail: 'test@example.com',
        ownerName: 'Test Owner',
        tag: 'production',
        qualityProfile: 'high',
        complianceRegime: 'GDPR',
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/',
          params: expect.objectContaining({
            owner_email: 'test@example.com',
            owner_name: 'Test Owner',
            tag: 'production',
            quality_profile: 'high',
            compliance_regime: 'GDPR',
          }),
        })
      );
    });

    it('should list contracts with server filters', async () => {
      const expectedResponse = { count: 5, results: [] };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await contractsAPI.list({
        serverType: 's3',
        serverUrl: 'https://s3.example.com',
        minAvailability: 99.0,
        maxLatencyMs: 100,
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: expect.objectContaining({
            server_type: 's3',
            server_url: 'https://s3.example.com',
            min_availability: 99.0,
            max_latency_ms: 100,
          }),
        })
      );
    });

    it('should list contracts with model filter', async () => {
      const expectedResponse = { count: 3, results: [] };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await contractsAPI.list({
        modelName: 'UserModel',
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: expect.objectContaining({
            model_name: 'UserModel',
          }),
        })
      );
    });
  });

  describe('get', () => {
    it('should get contract by ID', async () => {
      const expectedResponse = {
        id: '123',
        status: 'ACTIVE',
        hub_contract_json: {},
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await contractsAPI.get('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/',
        })
      );
    });

    it('should throw NotFoundError for non-existent contract', async () => {
      const errorResponse = {
        response: {
          status: 404,
          data: {
            error: {
              code: 'NOT_FOUND',
              message: 'Contract not found',
              http_status: 404,
            },
          },
        },
        config: {},
        request: {},
      };

      // Get the response interceptor to manually call it
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Mock request to reject, then manually call interceptor to transform
      mockAxiosInstance.request.mockImplementation(() => {
        return Promise.reject(errorResponse);
      });
      
      // The interceptor will be called by axios, but since we're mocking, we need to simulate it
      // The client.request() will catch the rejection and throw it, which will be caught by the interceptor
      // Since we're mocking, we'll test the interceptor directly
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error).toBeInstanceOf(NotFoundError);
      }
    });
  });

  describe('create', () => {
    it('should create contract from ODCS format', async () => {
      const contractData = {
        apiVersion: 'odcs/v3',
        kind: 'DataContract',
        metadata: { name: 'test-contract' },
      };

      const expectedResponse = {
        id: '123',
        status: 'DRAFT',
        original_format: 'JSON',
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 201,
      });

      const result = await contractsAPI.create({
        originalRaw: JSON.stringify(contractData),
        originalFormat: 'JSON',
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'POST',
          url: 'contracts/',
          data: {
            original_raw: JSON.stringify(contractData),
            original_format: 'JSON',
          },
        })
      );
    });

    it('should create contract with asset ID', async () => {
      const expectedResponse = {
        id: '123',
        asset_id: 'asset-456',
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 201,
      });

      const result = await contractsAPI.create({
        originalRaw: '{"apiVersion": "odcs/v3"}',
        originalFormat: 'JSON',
        assetId: 'asset-456',
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          data: expect.objectContaining({
            asset_id: 'asset-456',
          }),
        })
      );
    });

    it('should throw ValidationError for invalid contract', async () => {
      const errorResponse = {
        response: {
          status: 400,
          data: {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Invalid contract format',
              http_status: 400,
            },
          },
        },
        config: {},
        request: {},
      };

      // Get the response interceptor
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Mock request to reject
      mockAxiosInstance.request.mockRejectedValueOnce(errorResponse);
      
      // Test the interceptor directly
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error).toBeInstanceOf(ValidationError);
      }
    });
  });

  describe('update', () => {
    it('should update contract with partial data', async () => {
      const expectedResponse = {
        id: '123',
        status: 'ACTIVE',
        updated_at: '2025-01-15T10:00:00Z',
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const result = await contractsAPI.update('123', {
        originalRaw: '{"updated": true}',
      });

      expect(result).toEqual(expectedResponse);
      // Verify the request was made
      expect(mockAxiosInstance.request).toHaveBeenCalled();
      const callArgs = mockAxiosInstance.request.mock.calls[0][0];
      expect(callArgs.method).toBe('PATCH');
      expect(callArgs.url).toBe('contracts/123/');
      // The API accepts camelCase, which gets transformed to snake_case by the backend
      expect(callArgs.data).toHaveProperty('originalRaw');
      expect(callArgs.data.originalRaw).toBe('{"updated": true}');
    });
  });

  describe('delete', () => {
    it('should delete contract (soft delete)', async () => {
      mockAxiosInstance.request.mockResolvedValueOnce({
        data: null,
        status: 204,
      });

      await contractsAPI.delete('123');

      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'DELETE',
          url: 'contracts/123/',
        })
      );
    });
  });

  describe('validate', () => {
    it('should validate contract', async () => {
      const expectedResponse = {
        valid: true,
        errors: [],
        warnings: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const result = await contractsAPI.validate('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'POST',
          url: 'contracts/123/validate/',
        })
      );
    });

    it('should return validation errors for invalid contract', async () => {
      const expectedResponse = {
        valid: false,
        errors: ['Field "name" is required'],
        warnings: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const result = await contractsAPI.validate('123');

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(1);
    });
  });

  describe('lint', () => {
    it('should lint contract', async () => {
      const expectedResponse = {
        linted: true,
        issues: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const result = await contractsAPI.lint('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'POST',
          url: 'contracts/123/lint/',
        })
      );
    });
  });

  describe('Helper Methods', () => {
    const mockContract = {
      id: '123',
      hub_contract_json: {
        contact: [{ name: 'John Doe', email: 'john@example.com' }],
        servers: [{ type: 's3', url: 'https://s3.example.com' }],
        terms: { title: 'Terms', url: 'https://example.com/terms' },
        definitions: [{ name: 'Definition1', type: 'string' }],
        lineage: { inputs: [] },
        servicelevels: [{ type: 'availability', value: 99.9 }],
        models: [{ name: 'UserModel', fields: [] }],
      },
    };

    it('should get contact objects', () => {
      const contacts = contractsAPI.getContact(mockContract);
      expect(contacts).toEqual([{ name: 'John Doe', email: 'john@example.com' }]);
    });

    it('should get server objects', () => {
      const servers = contractsAPI.getServers(mockContract);
      expect(servers).toEqual([{ type: 's3', url: 'https://s3.example.com' }]);
    });

    it('should get terms object', () => {
      const terms = contractsAPI.getTerms(mockContract);
      expect(terms).toEqual({ title: 'Terms', url: 'https://example.com/terms' });
    });

    it('should get definition objects', () => {
      const definitions = contractsAPI.getDefinitions(mockContract);
      expect(definitions).toEqual([{ name: 'Definition1', type: 'string' }]);
    });

    it('should get lineage object', () => {
      const lineage = contractsAPI.getLineage(mockContract);
      expect(lineage).toEqual({ inputs: [] });
    });

    it('should get service level objects', () => {
      const serviceLevels = contractsAPI.getServiceLevels(mockContract);
      expect(serviceLevels).toEqual([{ type: 'availability', value: 99.9 }]);
    });

    it('should get models', () => {
      const models = contractsAPI.getModels(mockContract);
      expect(models).toEqual([{ name: 'UserModel', fields: [] }]);
    });

    it('should return null for missing objects', () => {
      const emptyContract = { id: '123', hub_contract_json: {} };
      expect(contractsAPI.getContact(emptyContract)).toBeNull();
      expect(contractsAPI.getServers(emptyContract)).toBeNull();
      expect(contractsAPI.getTerms(emptyContract)).toBeNull();
    });
  });
});

