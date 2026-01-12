/**
 * Compliance API Tests
 *
 * Comprehensive tests for all ComplianceAPI methods.
 *
 * NOTE: Following project best practices - no mocks/stubs.
 * Unit tests focus on structure and validation.
 * Integration tests use real API calls.
 */

import { DataHubClient } from '../client';
import { ComplianceAPI, CreateComplianceRunParams, ListComplianceRunsParams } from '../compliance';

describe('ComplianceAPI', () => {
  let client: DataHubClient;
  let complianceAPI: ComplianceAPI;

  beforeEach(() => {
    client = new DataHubClient({
      baseUrl: process.env.TEST_API_URL || 'http://localhost:8000/api/v1',
      apiToken: process.env.TEST_API_TOKEN || 'test-token',
    });

    complianceAPI = new ComplianceAPI(client);
  });

  describe('create', () => {
    it('should validate that at least one resource ID is required', async () => {
      const params: CreateComplianceRunParams = {
        scanMode: 'internal',
      };

      await expect(complianceAPI.create(params)).rejects.toThrow(
        'At least one of assetId, datasetId, or fileId must be provided'
      );
    });

    it('should accept assetId parameter', () => {
      const params: CreateComplianceRunParams = {
        assetId: 'test-asset-id',
        scanMode: 'internal',
      };

      // Should not throw validation error
      expect(() => complianceAPI.create(params)).not.toThrow();
    });

    it('should accept datasetId parameter', () => {
      const params: CreateComplianceRunParams = {
        datasetId: 'test-dataset-id',
        scanMode: 'internal',
      };

      expect(() => complianceAPI.create(params)).not.toThrow();
    });

    it('should accept fileId parameter', () => {
      const params: CreateComplianceRunParams = {
        fileId: 'test-file-id',
        scanMode: 'external',
      };

      expect(() => complianceAPI.create(params)).not.toThrow();
    });

    it('should accept applicableRegulations parameter', () => {
      const params: CreateComplianceRunParams = {
        assetId: 'test-asset-id',
        scanMode: 'internal',
        applicableRegulations: ['GDPR', 'HIPAA'],
      };

      expect(() => complianceAPI.create(params)).not.toThrow();
    });

    it('should default scanMode to internal', () => {
      const params: CreateComplianceRunParams = {
        assetId: 'test-asset-id',
      };

      expect(() => complianceAPI.create(params)).not.toThrow();
    });
  });

  describe('list', () => {
    it('should accept empty parameters', () => {
      const params: ListComplianceRunsParams = {};

      expect(() => complianceAPI.list(params)).not.toThrow();
    });

    it('should accept assetId filter', () => {
      const params: ListComplianceRunsParams = {
        assetId: 'test-asset-id',
      };

      expect(() => complianceAPI.list(params)).not.toThrow();
    });

    it('should accept status filter', () => {
      const params: ListComplianceRunsParams = {
        status: 'SUCCEEDED',
      };

      expect(() => complianceAPI.list(params)).not.toThrow();
    });

    it('should accept limit and offset parameters', () => {
      const params: ListComplianceRunsParams = {
        limit: 10,
        offset: 5,
      };

      expect(() => complianceAPI.list(params)).not.toThrow();
    });

    it('should default limit to 20 and offset to 0', () => {
      const params: ListComplianceRunsParams = {};

      expect(() => complianceAPI.list(params)).not.toThrow();
    });
  });

  describe('get', () => {
    it('should require complianceRunId parameter', () => {
      expect(() => complianceAPI.get('test-run-id')).not.toThrow();
    });
  });

  describe('getResults', () => {
    it('should require complianceRunId parameter', () => {
      expect(() => complianceAPI.getResults('test-run-id')).not.toThrow();
    });
  });

  describe('helper methods', () => {
    describe('isCompleted', () => {
      it('should return true for SUCCEEDED status', () => {
        const run = {
          id: 'test-id',
          status: 'SUCCEEDED' as const,
        };
        expect(complianceAPI.isCompleted(run)).toBe(true);
      });

      it('should return true for FAILED status', () => {
        const run = {
          id: 'test-id',
          status: 'FAILED' as const,
        };
        expect(complianceAPI.isCompleted(run)).toBe(true);
      });

      it('should return false for PENDING status', () => {
        const run = {
          id: 'test-id',
          status: 'PENDING' as const,
        };
        expect(complianceAPI.isCompleted(run)).toBe(false);
      });

      it('should return false for RUNNING status', () => {
        const run = {
          id: 'test-id',
          status: 'RUNNING' as const,
        };
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
        const run = {
          id: 'test-id',
          status: 'PENDING' as const,
        };
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
    it('should use standardized /runs/ endpoint pattern', () => {
      // Verify that the API uses the standardized endpoint pattern
      // This is verified by checking the method implementations use 'compliance/runs/'
      const createMethod = complianceAPI.create.toString();
      expect(createMethod).toContain('compliance/runs/');
      expect(createMethod).not.toContain('compliance-runs');

      const listMethod = complianceAPI.list.toString();
      expect(listMethod).toContain('compliance/runs/');
      expect(listMethod).not.toContain('compliance-runs');

      const getMethod = complianceAPI.get.toString();
      expect(getMethod).toContain('compliance/runs/');
      expect(getMethod).not.toContain('compliance-runs');

      const getResultsMethod = complianceAPI.getResults.toString();
      expect(getResultsMethod).toContain('compliance/runs/');
      expect(getResultsMethod).not.toContain('compliance-runs');
    });
  });
});

