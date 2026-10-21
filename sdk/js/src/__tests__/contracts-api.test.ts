/**
 * Contracts API Tests — W6.2: rewritten against a real local HTTP
 * server; the wire shape (method, path, query, body) is asserted from
 * the server's record of what actually arrived.
 */

import { DataHubClient } from '../client';
import { ContractsAPI } from '../contracts';
import { ValidationError, NotFoundError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('ContractsAPI', () => {
  let server: TestServer;
  let client: DataHubClient;
  let contractsAPI: ContractsAPI;

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
  });

  const lastUrl = () => server.requests[server.requests.length - 1].url;
  const lastBody = () => JSON.parse(server.requests[server.requests.length - 1].body);
  const lastMethod = () => server.requests[server.requests.length - 1].method;

  describe('list', () => {
    it('should list contracts with default parameters', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          count: 100,
          page: 1,
          page_size: 50,
          results: [{ id: '123', status: 'ACTIVE' }],
        })
      );

      const result = await contractsAPI.list();

      expect(result.results).toEqual([{ id: '123', status: 'ACTIVE' }]);
      expect(lastMethod()).toBe('GET');
      expect(lastUrl()).toBe('/api/v1/contracts/?page=1&page_size=50');
    });

    it('should list contracts with pagination', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { count: 200, page: 2, page_size: 25, results: [] })
      );

      const result = await contractsAPI.list({ page: 2, pageSize: 25 });

      expect(result.page).toBe(2);
      expect(lastUrl()).toBe('/api/v1/contracts/?page=2&page_size=25');
    });

    it('should list contracts with filters', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          count: 10,
          results: [{ id: '123', owner_email: 'test@example.com' }],
        })
      );

      const result = await contractsAPI.list({
        ownerEmail: 'test@example.com',
        ownerName: 'Test Owner',
        tag: 'production',
        qualityProfile: 'high',
        complianceRegime: 'GDPR',
      });

      expect(result.results).toHaveLength(1);
      const url = lastUrl();
      expect(url).toContain('owner_email=test%40example.com');
      expect(url).toContain('owner_name=Test+Owner');
      expect(url).toContain('tag=production');
      expect(url).toContain('quality_profile=high');
      expect(url).toContain('compliance_regime=GDPR');
    });

    it('should list contracts with server filters', async () => {
      server.setHandler((req, res) => json(res, 200, { count: 5, results: [] }));

      await contractsAPI.list({
        serverType: 's3',
        serverUrl: 'https://s3.example.com',
        minAvailability: 99.0,
        maxLatencyMs: 100,
      });

      const url = lastUrl();
      expect(url).toContain('server_type=s3');
      expect(url).toContain('server_url=https%3A%2F%2Fs3.example.com');
      expect(url).toContain('min_availability=99');
      expect(url).toContain('max_latency_ms=100');
    });

    it('should list contracts with model filter', async () => {
      server.setHandler((req, res) => json(res, 200, { count: 3, results: [] }));

      await contractsAPI.list({ modelName: 'UserModel' });

      expect(lastUrl()).toContain('model_name=UserModel');
    });
  });

  describe('get', () => {
    it('should get contract by ID', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { id: '123', status: 'ACTIVE', hub_contract_json: {} })
      );

      const result = await contractsAPI.get('123');

      expect(result.id).toBe('123');
      expect(result.status).toBe('ACTIVE');
      expect(lastMethod()).toBe('GET');
      expect(lastUrl()).toBe('/api/v1/contracts/123/');
    });

    it('should throw NotFoundError for non-existent contract', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 404, 'NOT_FOUND', 'Contract not found');
      });

      await expect(contractsAPI.get('nope')).rejects.toBeInstanceOf(NotFoundError);
    });
  });

  describe('create', () => {
    it('should create contract from ODCS format', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: '123', status: 'DRAFT', original_format: 'JSON' })
      );

      const contractData = {
        apiVersion: 'odcs/v3',
        kind: 'DataContract',
        metadata: { name: 'test-contract' },
      };

      const result = await contractsAPI.create({
        originalRaw: JSON.stringify(contractData),
        originalFormat: 'JSON',
      });

      expect(result.id).toBe('123');
      expect(result.status).toBe('DRAFT');
      expect(lastMethod()).toBe('POST');
      expect(lastUrl()).toBe('/api/v1/contracts/');
      expect(lastBody()).toEqual({
        original_raw: JSON.stringify(contractData),
        original_format: 'JSON',
      });
    });

    it('should create contract with asset ID', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: '123', asset_id: 'asset-456' })
      );

      const result = await contractsAPI.create({
        originalRaw: '{"apiVersion": "odcs/v3"}',
        originalFormat: 'JSON',
        assetId: 'asset-456',
      });

      expect(result.assetId).toBe('asset-456');
      expect(lastBody()).toEqual(
        expect.objectContaining({ asset_id: 'asset-456' })
      );
    });

    it('should throw ValidationError for invalid contract', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid contract format');
      });

      await expect(
        contractsAPI.create({ originalRaw: '{}', originalFormat: 'JSON' })
      ).rejects.toBeInstanceOf(ValidationError);
    });
  });

  describe('update', () => {
    it('should update contract with partial data', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          id: '123',
          status: 'ACTIVE',
          updated_at: '2025-01-15T10:00:00Z',
        })
      );

      const result = await contractsAPI.update('123', {
        originalRaw: '{"updated": true}',
      });

      expect(result.id).toBe('123');
      expect(lastMethod()).toBe('PATCH');
      expect(lastUrl()).toBe('/api/v1/contracts/123/');
      // The camelCase body is snake-cased on the wire (118C.2).
      expect(lastBody()).toEqual({ original_raw: '{"updated": true}' });
    });
  });

  describe('delete', () => {
    it('should delete contract (soft delete)', async () => {
      server.setHandler((req, res) => {
        res.writeHead(204, { Connection: 'close' });
        res.end();
      });

      await contractsAPI.delete('123');

      expect(lastMethod()).toBe('DELETE');
      expect(lastUrl()).toBe('/api/v1/contracts/123/');
    });
  });

  describe('validate', () => {
    it('should validate contract', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { valid: true, errors: [], warnings: [] })
      );

      const result = await contractsAPI.validate('123');

      expect(result.valid).toBe(true);
      expect(lastMethod()).toBe('POST');
      expect(lastUrl()).toBe('/api/v1/contracts/123/validate/');
    });

    it('should return validation errors for invalid contract', async () => {
      server.setHandler((req, res) =>
        json(res, 200, {
          valid: false,
          errors: ['Field "name" is required'],
          warnings: [],
        })
      );

      const result = await contractsAPI.validate('123');

      expect(result.valid).toBe(false);
      expect(result.errors).toHaveLength(1);
    });
  });

  describe('lint', () => {
    it('should lint contract', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { linted: true, issues: [] })
      );

      const result = await contractsAPI.lint('123');

      expect(result.linted).toBe(true);
      expect(lastMethod()).toBe('POST');
      expect(lastUrl()).toBe('/api/v1/contracts/123/lint/');
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
