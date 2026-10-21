/**
 * Integration Tests — W6.2: complete workflows against a real local
 * HTTP server (the previous version drove mocked axios instances).
 */

import { DataHubClient } from '../client';
import { ContractsAPI } from '../contracts';
import { LineageAPI } from '../lineage';
import { ComplianceAPI } from '../compliance';
import { ValidationError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('Integration Tests', () => {
  let server: TestServer;
  let client: DataHubClient;
  let contractsAPI: ContractsAPI;
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

    contractsAPI = new ContractsAPI(client);
    lineageAPI = new LineageAPI(client);
  });

  describe('Client Initialization', () => {
    it('should initialize client with all API modules', () => {
      expect(client.contracts).not.toBeUndefined();
      expect(client.lineage).not.toBeUndefined();
      expect(client.compliance).not.toBeUndefined();
    });

    it('should allow access to APIs through client', () => {
      expect(client.contracts).toBeInstanceOf(ContractsAPI);
      expect(client.lineage).toBeInstanceOf(LineageAPI);
      expect(client.compliance).toBeInstanceOf(ComplianceAPI);
    });
  });

  describe('Complete Workflows', () => {
    it('should create contract and retrieve it', async () => {
      server.setHandler((req, res) => {
        if (req.method === 'POST' && req.url === '/api/v1/contracts/') {
          json(res, 201, { id: 'contract-123', status: 'DRAFT', original_format: 'JSON' });
        } else {
          json(res, 200, { id: 'contract-123', status: 'ACTIVE', hub_contract_json: {} });
        }
      });

      // Create contract
      const created = await contractsAPI.create({
        originalRaw: JSON.stringify({
          apiVersion: 'odcs/v3',
          kind: 'DataContract',
          metadata: { name: 'test-contract' },
        }),
        originalFormat: 'JSON',
      });

      expect(created.id).toBe('contract-123');

      // Retrieve contract
      const retrieved = await contractsAPI.get('contract-123');

      expect(retrieved.id).toBe('contract-123');
      expect(retrieved.status).toBe('ACTIVE');
    });

    it('should create contract, validate it, and get lineage', async () => {
      server.setHandler((req, res) => {
        if (req.url?.includes('/validate/')) {
          json(res, 200, { valid: true, errors: [], warnings: [] });
        } else if (req.url?.includes('/lineage/contracts/')) {
          json(res, 200, {
            contract_id: 'contract-123',
            upstream_contracts: [],
            downstream_contracts: [],
          });
        } else {
          json(res, 201, { id: 'contract-123', status: 'DRAFT' });
        }
      });

      // Create contract
      const created = await contractsAPI.create({
        originalRaw: JSON.stringify({
          apiVersion: 'odcs/v3',
          kind: 'DataContract',
          metadata: { name: 'test-contract' },
        }),
        originalFormat: 'JSON',
      });

      // Validate contract
      const validation = await contractsAPI.validate(created.id);
      expect(validation.valid).toBe(true);

      // Get lineage
      const lineage = await lineageAPI.getContractLineage(created.id);
      expect(lineage.contractId).toBe('contract-123');
    });

    it('should list contracts, filter, and get details', async () => {
      server.setHandler((req, res) => {
        if ((req.url || '').split('?')[0] === '/api/v1/contracts/') {
          json(res, 200, {
            count: 2,
            results: [
              { id: 'contract-1', status: 'ACTIVE' },
              { id: 'contract-2', status: 'DRAFT' },
            ],
          });
        } else {
          json(res, 200, {
            id: 'contract-1',
            status: 'ACTIVE',
            hub_contract_json: {
              contact: [{ name: 'John Doe', email: 'john@example.com' }],
            },
          });
        }
      });

      // List contracts
      const contracts = await contractsAPI.list({ page: 1, pageSize: 50 });

      expect(contracts.results).toHaveLength(2);
      expect(server.requests[0].url).toContain('page=1');
      expect(server.requests[0].url).toContain('page_size=50');

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
      server.setHandler((req, res) => {
        if (server.requests.length === 1) {
          errorEnvelope(res, 500, 'INTERNAL_ERROR', 'Server error');
        } else {
          json(res, 200, { id: 'contract-123', status: 'ACTIVE' });
        }
      });

      const result = await contractsAPI.get('contract-123');

      expect(result.id).toBe('contract-123');
      expect(server.requests).toHaveLength(2);
    });

    it('should handle validation errors gracefully', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid contract format', {
          details: {
            field_errors: [{ field: 'metadata.name', message: 'Name is required' }],
          },
        });
      });

      const error = await contractsAPI
        .create({ originalRaw: '{}', originalFormat: 'JSON' })
        .catch((e) => e);

      expect(error).toBeInstanceOf(ValidationError);
      expect(error.details).not.toBeUndefined();
      expect(error.details.field_errors).toHaveLength(1);
    });
  });

  describe('Multi-Step Operations', () => {
    it('should perform contract lifecycle operations', async () => {
      const seen: string[] = [];
      server.setHandler((req, res) => {
        seen.push(`${req.method} ${req.url}`);
        if (req.url?.includes('/validate/')) {
          json(res, 200, { valid: true, errors: [] });
        } else if (req.url?.includes('/lineage/contracts/')) {
          json(res, 200, { contract_id: 'contract-123', upstream_contracts: [] });
        } else if (req.method === 'POST') {
          json(res, 201, { id: 'contract-123', status: 'DRAFT' });
        } else if (req.method === 'PATCH') {
          json(res, 200, { id: 'contract-123', status: 'ACTIVE' });
        } else if (req.method === 'DELETE') {
          res.writeHead(204, { Connection: 'close' });
          res.end();
        } else {
          json(res, 200, { id: 'contract-123', status: 'ACTIVE' });
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
      expect(lineage.contractId).toBe('contract-123');
      expect(seen).toEqual([
        'POST /api/v1/contracts/',
        'PATCH /api/v1/contracts/contract-123/',
        'POST /api/v1/contracts/contract-123/validate/',
        'GET /api/v1/contracts/contract-123/lineage/contracts/',
        'DELETE /api/v1/contracts/contract-123/',
      ]);
    });
  });

  describe('Complex Lineage Queries', () => {
    it('should get full lineage hierarchy', async () => {
      server.setHandler((req, res) => {
        json(res, 200, {
          contract_id: 'contract-123',
          contracts: [{ id: 'upstream-1', name: 'Upstream Contract' }],
          models: [{ contract_id: 'contract-123', name: 'UserModel' }],
          fields: [
            { contract_id: 'contract-123', model_name: 'UserModel', field_name: 'email' },
          ],
        });
      });

      const lineage = await lineageAPI.getFullLineage('contract-123', {
        maxContractDepth: 5,
        maxModelDepth: 3,
        maxFieldDepth: 2,
      });

      expect(lineage.contractId).toBe('contract-123');
      expect(lineage.contracts).toHaveLength(1);
      expect(lineage.models).toHaveLength(1);
      expect(lineage.fields).toHaveLength(1);
      expect(server.requests[0].url).toContain('max_contract_depth=5');
      expect(server.requests[0].url).toContain('max_model_depth=3');
      expect(server.requests[0].url).toContain('max_field_depth=2');
    });

    it('should get impact analysis for contract changes', async () => {
      server.setHandler((req, res) => {
        json(res, 200, {
          contract_id: 'contract-123',
          impacted_contracts: [{ id: 'downstream-1', impact_level: 'HIGH' }],
          impacted_models: [{ contract_id: 'downstream-1', model_name: 'DependentModel' }],
          impacted_fields: [],
        });
      });

      const impact = await lineageAPI.getImpactAnalysis('contract-123', {
        depth: 5,
        includeFields: true,
      });

      expect(impact.contractId).toBe('contract-123');
      expect(impact.impactedContracts).toHaveLength(1);
      expect(impact.impactedModels).toHaveLength(1);
      expect(server.requests[0].url).toContain('depth=5');
      expect(server.requests[0].url).toContain('include_fields=true');
    });
  });
});
