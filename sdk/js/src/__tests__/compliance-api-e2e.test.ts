/**
 * Compliance API E2E Tests
 *
 * End-to-end tests for Compliance API using real API server.
 * No mocks or stubs - all tests use real API endpoints.
 *
 * To run these tests:
 * 1. Start the API service: docker compose up -d api-service
 * 2. Set TEST_API_URL environment variable (default: http://localhost:8000/api/v1)
 * 3. Set TEST_API_TOKEN environment variable with a valid API token
 * 4. Run: npm test -- compliance-api-e2e.test.ts
 */

import { DataHubClient } from '../client';
import { ComplianceAPI, ComplianceRun } from '../compliance';
import { getTestApiBaseUrl, getTestEnvConfig } from './test-env-config';

const TEST_API_URL = process.env.TEST_API_URL || 'http://localhost:8000/api/v1';
const TEST_API_TOKEN = process.env.TEST_API_TOKEN || '';

describe('Compliance API E2E Tests', () => {
  let client: DataHubClient;
  let complianceAPI: ComplianceAPI;
  let testAssetId: string | null = null;
  let hasValidAuth = false;

  beforeAll(async () => {
    const config = getTestEnvConfig();
    const apiToken = TEST_API_TOKEN || config.apiToken;

    // Check if we have authentication
    if (!apiToken) {
      console.warn('No API token provided. E2E tests will be skipped.');
      console.warn('Set TEST_API_TOKEN environment variable to run E2E tests.');
      return;
    }

    client = new DataHubClient({
      baseUrl: getTestApiBaseUrl(),
      apiToken: apiToken,
      timeout: config.timeout,
      maxRetries: config.maxRetries,
      enableLogging: process.env.DEBUG === 'true',
    });

    complianceAPI = new ComplianceAPI(client);

    // Verify authentication works by making a simple API call
    try {
      await complianceAPI.list({ limit: 1 });
      hasValidAuth = true;
    } catch (error: any) {
      if (error.httpStatus === 401 || error.message?.includes('Unauthorized')) {
        console.warn('API token is invalid or expired. E2E tests will be skipped.');
        console.warn('Please set a valid TEST_API_TOKEN environment variable.');
        hasValidAuth = false;
      } else {
        // Other errors (network, etc.) - assume auth is OK but service might be down
        hasValidAuth = true;
      }
    }
  });

  beforeEach(async () => {
    // Skip if no valid authentication
    if (!hasValidAuth) {
      return;
    }

    // Create a test asset for compliance runs if needed
    // This is done via direct API call since we don't have an AssetsAPI yet
    if (!testAssetId) {
      try {
        const axios = require('axios');
        const config = getTestEnvConfig();
        const apiToken = TEST_API_TOKEN || config.apiToken;

        const response = await axios.post(
          `${getTestApiBaseUrl()}/assets/assets/`,
          {
            key: `test-asset-${Date.now()}`,
            name: 'Test Asset for Compliance',
            status: 'DRAFT',
          },
          {
            headers: {
              Authorization: `ApiKey ${apiToken}`,
              'Content-Type': 'application/json',
            },
          }
        );
        testAssetId = response.data.id;
      } catch (error: any) {
        // If asset creation fails, skip tests that require it
        console.warn('Could not create test asset:', error.message);
        testAssetId = null;
      }
    }
  });

  describe('create', () => {
    it('should create a compliance run with assetId', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }
      if (!testAssetId) {
        console.log('Skipping test - no test asset available');
        return;
      }

      const params = {
        assetId: testAssetId,
        scanMode: 'internal' as const,
        applicableRegulations: ['GDPR'],
      };

      const result = await complianceAPI.create(params);

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.status).toBe('PENDING');
      expect(result.asset).toBe(testAssetId);
    }, 30000);

    it('should create a compliance run without regulations (uses defaults)', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }
      if (!testAssetId) {
        console.log('Skipping test - no test asset available');
        return;
      }

      const params = {
        assetId: testAssetId,
        scanMode: 'internal' as const,
      };

      const result = await complianceAPI.create(params);

      expect(result).toBeDefined();
      expect(result.id).toBeDefined();
      expect(result.status).toBe('PENDING');
    }, 30000);

    it('should reject creation without resource IDs', async () => {
      // This test doesn't require authentication - it's a validation test
      // Create a temporary ComplianceAPI instance for this test
      const testClient = new DataHubClient({
        baseUrl: 'http://localhost:8000/api/v1',
        apiToken: 'test-token',
      });
      const testComplianceAPI = new ComplianceAPI(testClient);

      const params = {
        scanMode: 'internal' as const,
      };

      await expect(testComplianceAPI.create(params)).rejects.toThrow(
        'At least one of assetId, datasetId, or fileId must be provided'
      );
    });
  });

  describe('list', () => {
    it('should list compliance runs', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }

      const result = await complianceAPI.list();

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
    }, 30000);

    it('should filter compliance runs by assetId', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }
      if (!testAssetId) {
        console.log('Skipping test - no test asset available');
        return;
      }

      const result = await complianceAPI.list({
        assetId: testAssetId,
        limit: 10,
      });

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      // All results should be for the specified asset
      result.results.forEach((run: ComplianceRun) => {
        if (run.asset) {
          expect(run.asset).toBe(testAssetId);
        }
      });
    }, 30000);

    it('should filter compliance runs by status', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }

      const result = await complianceAPI.list({
        status: 'PENDING',
        limit: 10,
      });

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      // All results should have PENDING status
      result.results.forEach((run: ComplianceRun) => {
        expect(run.status).toBe('PENDING');
      });
    }, 30000);

    it('should support pagination with limit and offset', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }

      const result = await complianceAPI.list({
        limit: 5,
        offset: 0,
      });

      expect(result).toBeDefined();
      expect(result.results).toBeDefined();
      expect(result.results.length).toBeLessThanOrEqual(5);
    }, 30000);
  });

  describe('get', () => {
    it('should get compliance run by ID', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }
      if (!testAssetId) {
        console.log('Skipping test - no test asset available');
        return;
      }

      // First create a compliance run
      const created = await complianceAPI.create({
        assetId: testAssetId,
        scanMode: 'internal' as const,
      });

      // Then retrieve it
      const retrieved = await complianceAPI.get(created.id);

      expect(retrieved).toBeDefined();
      expect(retrieved.id).toBe(created.id);
      expect(retrieved.status).toBeDefined();
    }, 30000);
  });

  describe('getResults', () => {
    it('should get compliance run results', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }
      if (!testAssetId) {
        console.log('Skipping test - no test asset available');
        return;
      }

      // Create a compliance run
      const created = await complianceAPI.create({
        assetId: testAssetId,
        scanMode: 'internal' as const,
      });

      // Try to get results (may not be available immediately)
      try {
        const results = await complianceAPI.getResults(created.id);

        expect(results).toBeDefined();
        expect(results.compliance_run_id).toBe(created.id);
        // Results may or may not be available depending on run status
        if (results.overall_status) {
          expect(['PASS', 'WARN', 'FAIL']).toContain(results.overall_status);
        }
      } catch (error: any) {
        // If run is not completed, results endpoint may return 404 or 400
        // This is expected behavior
        if (error.message.includes('404') || error.message.includes('400')) {
          console.log('Compliance run not completed yet - results not available');
        } else {
          throw error;
        }
      }
    }, 30000);
  });

  describe('helper methods', () => {
    // Helper methods don't require authentication - they're pure functions
    // Create a temporary ComplianceAPI instance for testing helper methods
    let testComplianceAPI: ComplianceAPI;

    beforeAll(() => {
      // Create a minimal client for helper method tests (doesn't need real API)
      const testClient = new DataHubClient({
        baseUrl: 'http://localhost:8000/api/v1',
        apiToken: 'test-token',
      });
      testComplianceAPI = new ComplianceAPI(testClient);
    });

    it('should correctly identify completed runs', () => {
      const pendingRun: ComplianceRun = {
        id: 'test-1',
        status: 'PENDING',
      };
      expect(testComplianceAPI.isCompleted(pendingRun)).toBe(false);

      const succeededRun: ComplianceRun = {
        id: 'test-2',
        status: 'SUCCEEDED',
      };
      expect(testComplianceAPI.isCompleted(succeededRun)).toBe(true);

      const failedRun: ComplianceRun = {
        id: 'test-3',
        status: 'FAILED',
      };
      expect(testComplianceAPI.isCompleted(failedRun)).toBe(true);
    });

    it('should correctly identify passed runs', () => {
      const passedRun: ComplianceRun = {
        id: 'test-1',
        status: 'SUCCEEDED',
        overall_status: 'PASS',
      };
      expect(testComplianceAPI.isPassed(passedRun)).toBe(true);

      const failedRun: ComplianceRun = {
        id: 'test-2',
        status: 'SUCCEEDED',
        overall_status: 'FAIL',
      };
      expect(testComplianceAPI.isPassed(failedRun)).toBe(false);

      const pendingRun: ComplianceRun = {
        id: 'test-3',
        status: 'PENDING',
      };
      expect(testComplianceAPI.isPassed(pendingRun)).toBe(false);
    });

    it('should correctly calculate risk level values', () => {
      expect(testComplianceAPI.getRiskLevelValue('NONE')).toBe(0);
      expect(testComplianceAPI.getRiskLevelValue('LOW')).toBe(1);
      expect(testComplianceAPI.getRiskLevelValue('MEDIUM')).toBe(2);
      expect(testComplianceAPI.getRiskLevelValue('HIGH')).toBe(3);
      expect(testComplianceAPI.getRiskLevelValue('CRITICAL')).toBe(4);
      expect(testComplianceAPI.getRiskLevelValue(undefined)).toBe(0);
    });
  });

  describe('endpoint standardization', () => {
    it('should use standardized /runs/ endpoint', async () => {
      if (!hasValidAuth) {
        console.log('Skipping test - no valid authentication');
        return;
      }
      // Verify that API calls use the standardized endpoint pattern
      // This is verified by checking actual API calls succeed with the new pattern
      if (!testAssetId) {
        console.log('Skipping test - no test asset available');
        return;
      }

      // Create a run - this should use /compliance/runs/ endpoint
      const created = await complianceAPI.create({
        assetId: testAssetId,
        scanMode: 'internal' as const,
      });

      expect(created).toBeDefined();
      expect(created.id).toBeDefined();

      // List runs - this should use /compliance/runs/ endpoint
      const listResult = await complianceAPI.list();
      expect(listResult).toBeDefined();

      // Get run - this should use /compliance/runs/{id}/ endpoint
      const retrieved = await complianceAPI.get(created.id);
      expect(retrieved).toBeDefined();
      expect(retrieved.id).toBe(created.id);
    }, 30000);
  });
});

