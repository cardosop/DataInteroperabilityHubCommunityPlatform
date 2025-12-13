/**
 * Integration Tests
 * 
 * Tests for complete workflows, real API server, and mock server scenarios.
 */

import { DataHubClient } from '../client';
import { ContractsAPI } from '../contracts';
import { LineageAPI } from '../lineage';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('Integration Tests', () => {
  let client: DataHubClient;
  let contractsAPI: ContractsAPI;
  let lineageAPI: LineageAPI;
  const mockAxiosInstance = {
    request: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
    
    client = new DataHubClient({
      baseUrl: 'https://api.example.com/api/v1',
      apiToken: 'test-token',
    });
    
    contractsAPI = new ContractsAPI(client);
    lineageAPI = new LineageAPI(client);
  });

  describe('Client Initialization', () => {
    it('should initialize client with all API modules', () => {
      expect(client.contracts).toBeDefined();
      expect(client.lineage).toBeDefined();
    });

    it('should allow access to APIs through client', () => {
      expect(client.contracts).toBeInstanceOf(ContractsAPI);
      expect(client.lineage).toBeInstanceOf(LineageAPI);
    });
  });

  describe('Complete Workflows', () => {
    it('should create contract and retrieve it', async () => {
      const contractData = {
        apiVersion: 'odcs/v3',
        kind: 'DataContract',
        metadata: { name: 'test-contract' },
      };

      const createResponse = {
        id: 'contract-123',
        status: 'DRAFT',
        original_format: 'JSON',
      };

      const getResponse = {
        id: 'contract-123',
        status: 'ACTIVE',
        hub_contract_json: {},
      };

      mockAxiosInstance.request
        .mockResolvedValueOnce({ data: createResponse, status: 201 })
        .mockResolvedValueOnce({ data: getResponse, status: 200 });

      // Create contract
      const created = await contractsAPI.create({
        originalRaw: JSON.stringify(contractData),
        originalFormat: 'JSON',
      });

      expect(created.id).toBe('contract-123');

      // Retrieve contract
      const retrieved = await contractsAPI.get('contract-123');

      expect(retrieved.id).toBe('contract-123');
      expect(retrieved.status).toBe('ACTIVE');
    });

    it('should create contract, validate it, and get lineage', async () => {
      const contractData = {
        apiVersion: 'odcs/v3',
        kind: 'DataContract',
        metadata: { name: 'test-contract' },
      };

      const createResponse = {
        id: 'contract-123',
        status: 'DRAFT',
      };

      const validateResponse = {
        valid: true,
        errors: [],
        warnings: [],
      };

      const lineageResponse = {
        contract_id: 'contract-123',
        upstream_contracts: [],
        downstream_contracts: [],
      };

      mockAxiosInstance.request
        .mockResolvedValueOnce({ data: createResponse, status: 201 })
        .mockResolvedValueOnce({ data: validateResponse, status: 200 })
        .mockResolvedValueOnce({ data: lineageResponse, status: 200 });

      // Create contract
      const created = await contractsAPI.create({
        originalRaw: JSON.stringify(contractData),
        originalFormat: 'JSON',
      });

      // Validate contract
      const validation = await contractsAPI.validate(created.id);
      expect(validation.valid).toBe(true);

      // Get lineage
      const lineage = await lineageAPI.getContractLineage(created.id);
      expect(lineage.contract_id).toBe('contract-123');
    });

    it('should list contracts, filter, and get details', async () => {
      const listResponse = {
        count: 2,
        results: [
          { id: 'contract-1', status: 'ACTIVE' },
          { id: 'contract-2', status: 'DRAFT' },
        ],
      };

      const getResponse = {
        id: 'contract-1',
        status: 'ACTIVE',
        hub_contract_json: {
          contact: [{ name: 'John Doe', email: 'john@example.com' }],
        },
      };

      mockAxiosInstance.request
        .mockResolvedValueOnce({ data: listResponse, status: 200 })
        .mockResolvedValueOnce({ data: getResponse, status: 200 });

      // List contracts
      const contracts = await contractsAPI.list({ page: 1, pageSize: 50 });

      expect(contracts.results).toHaveLength(2);

      // Get first contract details
      const details = await contractsAPI.get('contract-1');

      expect(details.id).toBe('contract-1');
      
      // Use helper method to get contact
      const contacts = contractsAPI.getContact(details);
      expect(contacts).toEqual([{ name: 'John Doe', email: 'john@example.com' }]);
    });
  });

  describe('Error Recovery Workflows', () => {
    it('should retry and recover from transient errors', async () => {
      const serverError = {
        response: {
          status: 500,
          data: {
            error: {
              code: 'INTERNAL_ERROR',
              message: 'Server error',
              http_status: 500,
            },
          },
        },
        config: {},
        request: {},
      };

      const successResponse = {
        data: { id: 'contract-123', status: 'ACTIVE' },
        status: 200,
        headers: {},
        config: {},
      };

      let callCount = 0;
      mockAxiosInstance.request.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(serverError);
        }
        return Promise.resolve(successResponse);
      });

      jest.useFakeTimers();
      
      const promise = contractsAPI.get('contract-123');
      
      // Fast-forward through retry delay using runAllTimersAsync for async code
      await jest.runAllTimersAsync();
      
      const result = await promise;
      
      expect(result.id).toBe('contract-123');
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(2);
      
      jest.useRealTimers();
    });

    it('should handle validation errors gracefully', async () => {
      const errorResponse = {
        response: {
          status: 400,
          data: {
            error: {
              code: 'VALIDATION_ERROR',
              message: 'Invalid contract format',
              http_status: 400,
              details: {
                field_errors: [
                  { field: 'metadata.name', message: 'Name is required' },
                ],
              },
            },
          },
        },
        config: {},
        request: {},
      };

      // Get the response interceptor
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Test the interceptor directly
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error.httpStatus).toBe(400);
        expect(error.details).toBeDefined();
        expect(error.details.field_errors).toHaveLength(1);
      }
    });
  });

  describe('Multi-Step Operations', () => {
    it('should perform contract lifecycle operations', async () => {
      // Create
      const createResponse = { id: 'contract-123', status: 'DRAFT' };
      // Update
      const updateResponse = { id: 'contract-123', status: 'ACTIVE' };
      // Validate
      const validateResponse = { valid: true, errors: [] };
      // Get lineage
      const lineageResponse = {
        contract_id: 'contract-123',
        upstream_contracts: [],
      };

      let callCount = 0;
      mockAxiosInstance.request.mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({
            data: createResponse,
            status: 201,
            headers: {},
            config: {},
          });
        } else if (callCount === 2) {
          return Promise.resolve({
            data: updateResponse,
            status: 200,
            headers: {},
            config: {},
          });
        } else if (callCount === 3) {
          return Promise.resolve({
            data: validateResponse,
            status: 200,
            headers: {},
            config: {},
          });
        } else if (callCount === 4) {
          return Promise.resolve({
            data: lineageResponse,
            status: 200,
            headers: {},
            config: {},
          });
        } else {
          return Promise.resolve({
            data: null,
            status: 204,
            headers: {},
            config: {},
          });
        }
      });

      const created = await contractsAPI.create({
        originalRaw: '{"apiVersion": "odcs/v3"}',
        originalFormat: 'JSON',
      });

      const updated = await contractsAPI.update('contract-123', {
        originalRaw: '{"apiVersion": "odcs/v3", "updated": true}',
      });

      const validation = await contractsAPI.validate('contract-123');

      const lineage = await lineageAPI.getContractLineage('contract-123');

      await contractsAPI.delete('contract-123');

      expect(created.id).toBe('contract-123');
      expect(updated.status).toBe('ACTIVE');
      expect(validation.valid).toBe(true);
      expect(lineage.contract_id).toBe('contract-123');
    });
  });

  describe('Complex Lineage Queries', () => {
    it('should get full lineage hierarchy', async () => {
      const fullLineageResponse = {
        contract_id: 'contract-123',
        contracts: [
          { id: 'upstream-1', name: 'Upstream Contract' },
        ],
        models: [
          { contract_id: 'contract-123', name: 'UserModel' },
        ],
        fields: [
          {
            contract_id: 'contract-123',
            model_name: 'UserModel',
            field_name: 'email',
          },
        ],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: fullLineageResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const lineage = await lineageAPI.getFullLineage('contract-123', {
        maxContractDepth: 5,
        maxModelDepth: 3,
        maxFieldDepth: 2,
      });

      expect(lineage.contract_id).toBe('contract-123');
      expect(lineage.contracts).toHaveLength(1);
      expect(lineage.models).toHaveLength(1);
      expect(lineage.fields).toHaveLength(1);
    });

    it('should get impact analysis for contract changes', async () => {
      const impactResponse = {
        contract_id: 'contract-123',
        impacted_contracts: [
          { id: 'downstream-1', impact_level: 'HIGH' },
        ],
        impacted_models: [
          { contract_id: 'downstream-1', model_name: 'DependentModel' },
        ],
        impacted_fields: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: impactResponse,
        status: 200,
        headers: {},
        config: {},
      });

      const impact = await lineageAPI.getImpactAnalysis('contract-123', {
        depth: 5,
        includeFields: true,
      });

      expect(impact.contract_id).toBe('contract-123');
      expect(impact.impacted_contracts).toHaveLength(1);
      expect(impact.impacted_models).toHaveLength(1);
    });
  });
});

