/**
 * Lineage API Tests
 * 
 * Comprehensive tests for all LineageAPI methods.
 */

import { DataHubClient } from '../client';
import { LineageAPI } from '../lineage';
import { NotFoundError } from '../errors';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('LineageAPI', () => {
  let client: DataHubClient;
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
    
    lineageAPI = new LineageAPI(client);
  });

  describe('getContractLineage', () => {
    it('should get contract-level lineage', async () => {
      const expectedResponse = {
        contract_id: '123',
        upstream_contracts: [{ id: 'upstream-1' }],
        downstream_contracts: [{ id: 'downstream-1' }],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getContractLineage('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/lineage/contracts/',
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

      // Get the response interceptor
      const responseInterceptor = mockAxiosInstance.interceptors.response.use.mock.calls[0][1];
      
      // Test the interceptor directly
      try {
        await responseInterceptor(errorResponse);
        fail('Should have thrown error');
      } catch (error: any) {
        expect(error).toBeInstanceOf(NotFoundError);
      }
    });
  });

  describe('getModelLineage', () => {
    it('should get model-level lineage', async () => {
      const expectedResponse = {
        contract_id: '123',
        model_name: 'UserModel',
        upstream_models: [{ contract_id: 'upstream-1', model_name: 'SourceModel' }],
        downstream_models: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getModelLineage('123', 'UserModel');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/models/UserModel/lineage/',
        })
      );
    });
  });

  describe('getFieldLineage', () => {
    it('should get field-level lineage', async () => {
      const expectedResponse = {
        contract_id: '123',
        model_name: 'UserModel',
        field_name: 'email',
        upstream_fields: [
          {
            contract_id: 'upstream-1',
            model_name: 'SourceModel',
            field_name: 'user_email',
          },
        ],
        downstream_fields: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getFieldLineage('123', 'UserModel', 'email');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/fields/UserModel/email/lineage/',
        })
      );
    });
  });

  describe('getFullLineage', () => {
    it('should get complete hierarchical lineage with default parameters', async () => {
      const expectedResponse = {
        contract_id: '123',
        contracts: [],
        models: [],
        fields: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getFullLineage('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/lineage/full/',
          params: {
            max_contract_depth: 10,
            max_model_depth: 10,
            max_field_depth: 10,
          },
        })
      );
    });

    it('should get full lineage with custom depth parameters', async () => {
      const expectedResponse = {
        contract_id: '123',
        contracts: [],
        models: [],
        fields: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getFullLineage('123', {
        maxContractDepth: 5,
        maxModelDepth: 3,
        maxFieldDepth: 2,
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: {
            max_contract_depth: 5,
            max_model_depth: 3,
            max_field_depth: 2,
          },
        })
      );
    });
  });

  describe('getVisualization', () => {
    it('should get lineage visualization in JSON format', async () => {
      const expectedResponse = {
        nodes: [{ id: '123', label: 'Contract' }],
        edges: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getVisualization('123', 'json');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/lineage/visualization/',
          params: { format: 'json' },
        })
      );
    });

    it('should get lineage visualization in DOT format', async () => {
      const expectedResponse = 'digraph { node1 -> node2; }';

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getVisualization('123', 'dot');

      expect(result).toEqual({
        format: 'dot',
        content: expectedResponse,
      });
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: { format: 'dot' },
        })
      );
    });

    it('should get lineage visualization in Mermaid format', async () => {
      const expectedResponse = 'graph TD; A --> B;';

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getVisualization('123', 'mermaid');

      expect(result).toEqual({
        format: 'mermaid',
        content: expectedResponse,
      });
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: { format: 'mermaid' },
        })
      );
    });

    it('should default to JSON format', async () => {
      const expectedResponse = { nodes: [], edges: [] };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getVisualization('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: { format: 'json' },
        })
      );
    });
  });

  describe('getImpactAnalysis', () => {
    it('should get impact analysis with default parameters', async () => {
      const expectedResponse = {
        contract_id: '123',
        impacted_contracts: [],
        impacted_models: [],
        impacted_fields: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getImpactAnalysis('123');

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'GET',
          url: 'contracts/123/impact-analysis/',
          params: {
            depth: 10,
            include_fields: true,
          },
        })
      );
    });

    it('should get impact analysis with custom parameters', async () => {
      const expectedResponse = {
        contract_id: '123',
        impacted_contracts: [],
        impacted_models: [],
        impacted_fields: [],
      };

      mockAxiosInstance.request.mockResolvedValueOnce({
        data: expectedResponse,
        status: 200,
      });

      const result = await lineageAPI.getImpactAnalysis('123', {
        depth: 5,
        includeFields: false,
      });

      expect(result).toEqual(expectedResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          params: {
            depth: 5,
            include_fields: false,
          },
        })
      );
    });
  });
});

