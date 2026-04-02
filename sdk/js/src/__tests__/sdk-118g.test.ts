/**
 * Phase 118G — JS SDK Full Parity Tests
 *
 * Tests all 22 new modules are importable with correct class names,
 * all error classes exist with correct hierarchy,
 * and client mounts all modules.
 */

import axios from 'axios';
import { DataHubClient } from '../client';

jest.mock('axios');

describe('Phase 118G — JS SDK Full Parity', () => {
  let mockAxiosInstance: any;

  beforeEach(() => {
    jest.clearAllMocks();
    mockAxiosInstance = {
      request: jest.fn(),
      interceptors: {
        request: { use: jest.fn() },
        response: { use: jest.fn() },
      },
    };
    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);
  });

  describe('New modules importable', () => {
    it('GovernanceAPI', () => {
      const { GovernanceAPI } = require('../governance');
      expect(GovernanceAPI).not.toBeUndefined();
    });
    it('MeshAPI', () => {
      const { MeshAPI } = require('../mesh');
      expect(MeshAPI).not.toBeUndefined();
    });
    it('VirtualizationAPI', () => {
      const { VirtualizationAPI } = require('../virtualization');
      expect(VirtualizationAPI).not.toBeUndefined();
    });
    it('WebhooksAPI', () => {
      const { WebhooksAPI } = require('../webhooks');
      expect(WebhooksAPI).not.toBeUndefined();
    });
    it('MarketplaceAPI', () => {
      const { MarketplaceAPI } = require('../marketplace');
      expect(MarketplaceAPI).not.toBeUndefined();
    });
    it('BaaSAPI', () => {
      const { BaaSAPI } = require('../baas');
      expect(BaaSAPI).not.toBeUndefined();
    });
    it('MLAPI', () => {
      const { MLAPI } = require('../ml');
      expect(MLAPI).not.toBeUndefined();
    });
    it('ScheduledIngestionAPI', () => {
      const { ScheduledIngestionAPI } = require('../scheduledIngestion');
      expect(ScheduledIngestionAPI).not.toBeUndefined();
    });
    it('ScheduledExportAPI', () => {
      const { ScheduledExportAPI } = require('../scheduledExport');
      expect(ScheduledExportAPI).not.toBeUndefined();
    });
    it('VersioningAPI', () => {
      const { VersioningAPI } = require('../versioning');
      expect(VersioningAPI).not.toBeUndefined();
    });
    it('BillingAPI', () => {
      const { BillingAPI } = require('../billing');
      expect(BillingAPI).not.toBeUndefined();
    });
    it('SearchAPI', () => {
      const { SearchAPI } = require('../search');
      expect(SearchAPI).not.toBeUndefined();
    });
    it('ObservabilityAPI', () => {
      const { ObservabilityAPI } = require('../observability');
      expect(ObservabilityAPI).not.toBeUndefined();
    });
    it('GDPRAPI', () => {
      const { GDPRAPI } = require('../gdpr');
      expect(GDPRAPI).not.toBeUndefined();
    });
    it('TenantsAPI', () => {
      const { TenantsAPI } = require('../tenants');
      expect(TenantsAPI).not.toBeUndefined();
    });
    it('TransformationAPI', () => {
      const { TransformationAPI } = require('../transformation');
      expect(TransformationAPI).not.toBeUndefined();
    });
    it('SemanticAPI', () => {
      const { SemanticAPI } = require('../semantic');
      expect(SemanticAPI).not.toBeUndefined();
    });
    it('DatasetsAPI', () => {
      const { DatasetsAPI } = require('../datasets');
      expect(DatasetsAPI).not.toBeUndefined();
    });
    it('AssetsAPI', () => {
      const { AssetsAPI } = require('../assets');
      expect(AssetsAPI).not.toBeUndefined();
    });
    it('FilesAPI', () => {
      const { FilesAPI } = require('../files');
      expect(FilesAPI).not.toBeUndefined();
    });
    it('DQAPI', () => {
      const { DQAPI } = require('../dq');
      expect(DQAPI).not.toBeUndefined();
    });
    it('WorkflowsAPI', () => {
      const { WorkflowsAPI } = require('../workflows');
      expect(WorkflowsAPI).not.toBeUndefined();
    });
  });

  describe('Error classes', () => {
    it('BillingError hierarchy', () => {
      const {
        BillingError,
        BillingValidationError,
        DowngradeLimitExceededError,
        DataHubError,
      } = require('../errors');

      const e1 = new BillingError('test');
      expect(e1).toBeInstanceOf(DataHubError);
      expect(e1.code).toBe('BILLING_ERROR');

      const e2 = new BillingValidationError('test');
      expect(e2).toBeInstanceOf(BillingError);

      const e3 = new DowngradeLimitExceededError('test');
      expect(e3).toBeInstanceOf(BillingError);
    });

    it('Semantic error hierarchy', () => {
      const { SemanticError, SPARQLError, SHACLValidationError } = require('../errors');
      expect(new SPARQLError('test')).toBeInstanceOf(SemanticError);
      expect(new SHACLValidationError('test')).toBeInstanceOf(SemanticError);
    });

    it('EntitlementRequiredError has 403 status', () => {
      const { EntitlementRequiredError, DataHubError } = require('../errors');
      const e = new EntitlementRequiredError();
      expect(e).toBeInstanceOf(DataHubError);
      expect(e.code).toBe('ENTITLEMENT_REQUIRED');
      expect(e.httpStatus).toBe(403);
    });

    it('CircuitBreakerOpenError is 503', () => {
      const { CircuitBreakerOpenError, ServerError } = require('../errors');
      const e = new CircuitBreakerOpenError();
      expect(e).toBeInstanceOf(ServerError);
      expect(e.httpStatus).toBe(503);
    });

    it('All 30 domain error classes exist', () => {
      const errors = require('../errors');
      const expected = [
        'BillingError', 'BillingValidationError', 'DowngradeLimitExceededError',
        'TransformationError', 'TransformationValidationError',
        'ComplianceError', 'ComplianceValidationError',
        'SemanticError', 'SPARQLError', 'SHACLValidationError',
        'WorkflowError', 'DLQError',
        'EntitlementRequiredError', 'CircuitBreakerOpenError', 'ModelDeploymentError',
        'MarketplaceError', 'MarketplaceValidationError',
        'BaaSError', 'BaaSValidationError',
        'ODHMLError', 'ODHMLValidationError',
        'GovernanceError', 'MeshError', 'VirtualizationError',
        'WebhookError', 'GDPRError',
        'ScheduledIngestionError', 'ScheduledExportError',
        'DQError', 'SearchError', 'ObservabilityError',
      ];
      for (const name of expected) {
        expect(errors[name]).not.toBeUndefined();
      }
    });
  });

  describe('Client mounts all modules', () => {
    it('all 25 modules are mounted', () => {
      const client = new DataHubClient({
        baseUrl: 'https://api.example.com',
        apiToken: 'test',
      });

      const modules = [
        'contracts', 'lineage', 'compliance',
        'governance', 'mesh', 'virtualization',
        'webhooks', 'marketplace', 'baas', 'ml',
        'scheduledIngestion', 'scheduledExport',
        'versioning', 'billing', 'search',
        'observability', 'gdpr', 'tenants',
        'transformation', 'semantic', 'datasets',
        'assets', 'files', 'dq', 'workflows',
      ];

      for (const mod of modules) {
        expect((client as any)[mod]).not.toBeUndefined();
      }
    });
  });

  describe('Exports from index', () => {
    it('all API classes exported', () => {
      const sdk = require('../index');
      const expected = [
        'GovernanceAPI', 'MeshAPI', 'VirtualizationAPI',
        'WebhooksAPI', 'MarketplaceAPI', 'BaaSAPI', 'MLAPI',
        'ScheduledIngestionAPI', 'ScheduledExportAPI',
        'VersioningAPI', 'BillingAPI', 'SearchAPI',
        'ObservabilityAPI', 'GDPRAPI', 'TenantsAPI',
        'TransformationAPI', 'SemanticAPI', 'DatasetsAPI',
        'AssetsAPI', 'FilesAPI', 'DQAPI', 'WorkflowsAPI',
      ];
      for (const name of expected) {
        expect(sdk[name]).not.toBeUndefined();
      }
    });
  });
});
