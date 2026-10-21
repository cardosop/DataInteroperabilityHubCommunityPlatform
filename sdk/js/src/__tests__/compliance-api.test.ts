/**
 * Compliance API Tests — W6.2: rewritten against a real local HTTP
 * server.
 *
 * Root fix on the way: the previous version "tested" parameter
 * acceptance with sync `expect(() => complianceAPI.create(params))
 * .not.toThrow()` — but create() returns a PROMISE, so the assertion
 * never saw the rejection and the fired request became an unhandled
 * promise rejection against localhost:8000 (the uncaught-exception
 * crash in the jest run).  Every accepting-path test now completes a
 * real round-trip and asserts what arrived on the wire.
 */

import { DataHubClient } from '../client';
import { ComplianceAPI, CreateComplianceRunParams } from '../compliance';
import { TestServer, startTestServer, json } from './helpers/testHttpServer';

describe('ComplianceAPI', () => {
  let server: TestServer;
  let client: DataHubClient;
  let complianceAPI: ComplianceAPI;

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
    complianceAPI = new ComplianceAPI(client);
  });

  const lastUrl = () => server.requests[server.requests.length - 1].url;
  const lastBody = () => JSON.parse(server.requests[server.requests.length - 1].body);

  describe('create', () => {
    it('should validate that at least one resource ID is required', async () => {
      const params: CreateComplianceRunParams = {
        scanMode: 'internal',
      };

      await expect(complianceAPI.create(params)).rejects.toThrow(
        'At least one of assetId, datasetId, or fileId must be provided'
      );
      // Client-side validation — nothing reached the wire.
      expect(server.requests).toHaveLength(0);
    });

    it('should accept assetId parameter', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: 'run-1', status: 'PENDING' })
      );

      const result = await complianceAPI.create({
        assetId: 'test-asset-id',
        scanMode: 'internal',
      });

      expect(result.id).toBe('run-1');
      expect(lastUrl()).toBe('/api/v1/compliance/runs/');
      expect(lastBody()).toEqual({ scan_mode: 'internal', asset_id: 'test-asset-id' });
    });

    it('should accept datasetId parameter', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: 'run-2', status: 'PENDING' })
      );

      await complianceAPI.create({
        datasetId: 'test-dataset-id',
        scanMode: 'internal',
      });

      expect(lastBody()).toEqual({ scan_mode: 'internal', dataset_id: 'test-dataset-id' });
    });

    it('should accept fileId parameter', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: 'run-3', status: 'PENDING' })
      );

      await complianceAPI.create({
        fileId: 'test-file-id',
        scanMode: 'external',
      });

      expect(lastBody()).toEqual({ scan_mode: 'external', file_id: 'test-file-id' });
    });

    it('should accept applicableRegulations parameter', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: 'run-4', status: 'PENDING' })
      );

      await complianceAPI.create({
        assetId: 'test-asset-id',
        scanMode: 'internal',
        applicableRegulations: ['GDPR', 'HIPAA'],
      });

      expect(lastBody()).toEqual({
        scan_mode: 'internal',
        asset_id: 'test-asset-id',
        applicable_regulations: ['GDPR', 'HIPAA'],
      });
    });

    it('should default scanMode to internal', async () => {
      server.setHandler((req, res) =>
        json(res, 201, { id: 'run-5', status: 'PENDING' })
      );

      await complianceAPI.create({ assetId: 'test-asset-id' });

      expect(lastBody()).toEqual({ scan_mode: 'internal', asset_id: 'test-asset-id' });
    });
  });

  describe('list', () => {
    it('should accept empty parameters and send defaults', async () => {
      server.setHandler((req, res) => json(res, 200, { count: 0, results: [] }));

      const result = await complianceAPI.list({});

      expect(result.results).toEqual([]);
      expect(lastUrl()).toBe('/api/v1/compliance/runs/?limit=20&offset=0');
    });

    it('should accept assetId filter', async () => {
      server.setHandler((req, res) => json(res, 200, { count: 0, results: [] }));

      await complianceAPI.list({ assetId: 'test-asset-id' });

      expect(lastUrl()).toContain('asset_id=test-asset-id');
    });

    it('should accept status filter', async () => {
      server.setHandler((req, res) => json(res, 200, { count: 0, results: [] }));

      await complianceAPI.list({ status: 'SUCCEEDED' });

      expect(lastUrl()).toContain('status=SUCCEEDED');
    });

    it('should accept limit and offset parameters', async () => {
      server.setHandler((req, res) => json(res, 200, { count: 0, results: [] }));

      await complianceAPI.list({ limit: 10, offset: 5 });

      expect(lastUrl()).toContain('limit=10');
      expect(lastUrl()).toContain('offset=5');
    });
  });

  describe('get', () => {
    it('should require complianceRunId parameter', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { id: 'test-run-id', status: 'SUCCEEDED' })
      );

      const result = await complianceAPI.get('test-run-id');

      expect(result.id).toBe('test-run-id');
      expect(lastUrl()).toBe('/api/v1/compliance/runs/test-run-id/');
    });
  });

  describe('getResults', () => {
    it('should require complianceRunId parameter', async () => {
      server.setHandler((req, res) =>
        json(res, 200, { compliance_run_id: 'test-run-id', overall_status: 'PASS' })
      );

      const result = await complianceAPI.getResults('test-run-id');

      expect(result.complianceRunId).toBe('test-run-id');
      expect(lastUrl()).toBe('/api/v1/compliance/runs/test-run-id/results/');
    });
  });

  describe('helper methods', () => {
    describe('isCompleted', () => {
      it('should return true for SUCCEEDED status', () => {
        const run = { id: 'test-id', status: 'SUCCEEDED' as const };
        expect(complianceAPI.isCompleted(run)).toBe(true);
      });

      it('should return true for FAILED status', () => {
        const run = { id: 'test-id', status: 'FAILED' as const };
        expect(complianceAPI.isCompleted(run)).toBe(true);
      });

      it('should return false for PENDING status', () => {
        const run = { id: 'test-id', status: 'PENDING' as const };
        expect(complianceAPI.isCompleted(run)).toBe(false);
      });

      it('should return false for RUNNING status', () => {
        const run = { id: 'test-id', status: 'RUNNING' as const };
        expect(complianceAPI.isCompleted(run)).toBe(false);
      });
    });

    describe('isPassed', () => {
      it('should return true for SUCCEEDED with PASS status', () => {
        const run = {
          id: 'test-id',
          status: 'SUCCEEDED' as const,
          overall_status: 'PASS',
        };
        expect(complianceAPI.isPassed(run)).toBe(true);
      });

      it('should return false for SUCCEEDED with FAIL status', () => {
        const run = {
          id: 'test-id',
          status: 'SUCCEEDED' as const,
          overall_status: 'FAIL',
        };
        expect(complianceAPI.isPassed(run)).toBe(false);
      });

      it('should return false for PENDING status', () => {
        const run = { id: 'test-id', status: 'PENDING' as const };
        expect(complianceAPI.isPassed(run)).toBe(false);
      });
    });

    describe('getRiskLevelValue', () => {
      it('should return correct numeric values for risk levels', () => {
        expect(complianceAPI.getRiskLevelValue('NONE')).toBe(0);
        expect(complianceAPI.getRiskLevelValue('LOW')).toBe(1);
        expect(complianceAPI.getRiskLevelValue('MEDIUM')).toBe(2);
        expect(complianceAPI.getRiskLevelValue('HIGH')).toBe(3);
        expect(complianceAPI.getRiskLevelValue('CRITICAL')).toBe(4);
      });

      it('should return 0 for undefined risk level', () => {
        expect(complianceAPI.getRiskLevelValue(undefined)).toBe(0);
      });
    });
  });

  describe('endpoint standardization', () => {
    it('should use the standardized /runs/ endpoint pattern for every method', async () => {
      server.setHandler((req, res) => {
        const path = (req.url || '').split('?')[0];
        if (req.method === 'POST' && path === '/api/v1/compliance/runs/') {
          json(res, 201, { id: 'run-1', status: 'PENDING' });
        } else if (path.includes('/results/')) {
          json(res, 200, { compliance_run_id: 'run-1', overall_status: 'PASS' });
        } else if (path === '/api/v1/compliance/runs/') {
          json(res, 200, { count: 0, results: [] });
        } else {
          json(res, 200, { id: 'run-1', status: 'PENDING' });
        }
      });

      await complianceAPI.create({ assetId: 'a-1' });
      await complianceAPI.list();
      await complianceAPI.get('run-1');
      await complianceAPI.getResults('run-1');

      const urls = server.requests.map((r) => r.url);
      expect(urls).toEqual([
        '/api/v1/compliance/runs/',
        '/api/v1/compliance/runs/?limit=20&offset=0',
        '/api/v1/compliance/runs/run-1/',
        '/api/v1/compliance/runs/run-1/results/',
      ]);
    });
  });
});
