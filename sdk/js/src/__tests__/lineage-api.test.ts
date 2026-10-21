/**
 * Lineage API Tests — W6.2: rewritten against a real local HTTP server;
 * wire shape asserted from the server's request record.
 */

import { DataHubClient } from '../client';
import { LineageAPI } from '../lineage';
import { NotFoundError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('LineageAPI', () => {
  let server: TestServer;
  let client: DataHubClient;
  let lineageAPI: LineageAPI;

  beforeAll(async () => {
    server = await startTestServer();
  });

  afterAll(async () => {
    await server.close();
  });

  beforeEach(() => {
    server.reset();
    client = new DataHubClient({
      baseUrl: `${server.baseUrl}/api/v1`,
      apiToken: 'test-token',
      backoffBaseMs: 1,
    });
    lineageAPI = new LineageAPI(client);
  });

  const lastUrl = () => server.requests[server.requests.length - 1].url;

  describe('getContractLineage', () => {
    it('should get contract-level lineage', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          upstream_contracts: [{ id: 'upstream-1' }],
          downstream_contracts: [{ id: 'downstream-1' }],
        })
      );

      const result = await lineageAPI.getContractLineage('123');

      expect(result.contractId).toBe('123');
      expect(result.upstreamContracts).toHaveLength(1);
      expect(result.downstreamContracts).toHaveLength(1);
      expect(lastUrl()).toBe('/api/v1/contracts/123/lineage/contracts/');
    });

    it('should throw NotFoundError for non-existent contract', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 404, 'NOT_FOUND', 'Contract not found');
      });

      await expect(lineageAPI.getContractLineage('nope')).rejects.toBeInstanceOf(
        NotFoundError
      );
    });
  });

  describe('getModelLineage', () => {
    it('should get model-level lineage', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          model_name: 'UserModel',
          upstream_models: [{ contract_id: 'upstream-1', model_name: 'SourceModel' }],
          downstream_models: [],
        })
      );

      const result = await lineageAPI.getModelLineage('123', 'UserModel');

      expect(result.modelName).toBe('UserModel');
      expect(result.upstreamModels).toHaveLength(1);
      expect(lastUrl()).toBe('/api/v1/contracts/123/models/UserModel/lineage/');
    });
  });

  describe('getFieldLineage', () => {
    it('should get field-level lineage', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          model_name: 'UserModel',
          field_name: 'email',
          upstream_fields: [
            { contract_id: 'upstream-1', model_name: 'SourceModel', field_name: 'user_email' },
          ],
          downstream_fields: [],
        })
      );

      const result = await lineageAPI.getFieldLineage('123', 'UserModel', 'email');

      expect(result.fieldName).toBe('email');
      expect(result.upstreamFields).toHaveLength(1);
      expect(lastUrl()).toBe('/api/v1/contracts/123/fields/UserModel/email/lineage/');
    });
  });

  describe('getFullLineage', () => {
    it('should get complete hierarchical lineage with default parameters', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          contracts: [],
          models: [],
          fields: [],
        })
      );

      const result = await lineageAPI.getFullLineage('123');

      expect(result.contractId).toBe('123');
      expect(lastUrl()).toBe(
        '/api/v1/contracts/123/lineage/full/?max_contract_depth=10&max_model_depth=10&max_field_depth=10'
      );
    });

    it('should get full lineage with custom depth parameters', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          contracts: [],
          models: [],
          fields: [],
        })
      );

      await lineageAPI.getFullLineage('123', {
        maxContractDepth: 5,
        maxModelDepth: 3,
        maxFieldDepth: 2,
      });

      expect(lastUrl()).toBe(
        '/api/v1/contracts/123/lineage/full/?max_contract_depth=5&max_model_depth=3&max_field_depth=2'
      );
    });
  });

  describe('getVisualization', () => {
    it('should get lineage visualization in JSON format', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { nodes: [{ id: '123', label: 'Contract' }], edges: [] })
      );

      const result = await lineageAPI.getVisualization('123', 'json');

      expect(result.nodes).toHaveLength(1);
      expect(lastUrl()).toBe('/api/v1/contracts/123/lineage/visualization/?format=json');
    });

    it('should get lineage visualization in DOT format', async () => {
      server.setHandler((req, res) => {
        res.writeHead(200, { 'Content-Type': 'text/plain', Connection: 'close' });
        res.end('digraph { node1 -> node2; }');
      });

      const result = await lineageAPI.getVisualization('123', 'dot');

      expect(result).toEqual({
        format: 'dot',
        content: 'digraph { node1 -> node2; }',
      });
      expect(lastUrl()).toContain('format=dot');
    });

    it('should get lineage visualization in Mermaid format', async () => {
      server.setHandler((req, res) => {
        res.writeHead(200, { 'Content-Type': 'text/plain', Connection: 'close' });
        res.end('graph TD; A --> B;');
      });

      const result = await lineageAPI.getVisualization('123', 'mermaid');

      expect(result).toEqual({
        format: 'mermaid',
        content: 'graph TD; A --> B;',
      });
      expect(lastUrl()).toContain('format=mermaid');
    });

    it('should default to JSON format', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { nodes: [], edges: [] })
      );

      const result = await lineageAPI.getVisualization('123');

      expect(result.nodes).toEqual([]);
      expect(lastUrl()).toContain('format=json');
    });
  });

  describe('getImpactAnalysis', () => {
    it('should get impact analysis with default parameters', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          impacted_contracts: [],
          impacted_models: [],
          impacted_fields: [],
        })
      );

      const result = await lineageAPI.getImpactAnalysis('123');

      expect(result.contractId).toBe('123');
      expect(lastUrl()).toBe(
        '/api/v1/contracts/123/impact-analysis/?depth=10&include_fields=true'
      );
    });

    it('should get impact analysis with custom parameters', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          contract_id: '123',
          impacted_contracts: [],
          impacted_models: [],
          impacted_fields: [],
        })
      );

      await lineageAPI.getImpactAnalysis('123', {
        depth: 5,
        includeFields: false,
      });

      expect(lastUrl()).toBe(
        '/api/v1/contracts/123/impact-analysis/?depth=5&include_fields=false'
      );
    });
  });
});
