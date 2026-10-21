/**
 * Phase 118G — JS SDK Full Parity Tests
 *
 * Tests all 22 new modules are importable with correct class names,
 * all error classes exist with correct hierarchy,
 * and client mounts all modules.
 *
 * W6.2: these tests never touched the network — the axios mock only
 * existed to construct the client.  The fetch client constructs without
 * side effects, so the mock is gone.
 */

import { DataHubClient } from '../client';
import { GovernanceAPI } from '../governance';
import { MeshAPI } from '../mesh';
import { VirtualizationAPI } from '../virtualization';
import { WebhooksAPI } from '../webhooks';
import { MarketplaceAPI } from '../marketplace';
import { BaaSAPI } from '../baas';
import { MLAPI } from '../ml';
import { ScheduledIngestionAPI } from '../scheduledIngestion';
import { ScheduledExportAPI } from '../scheduledExport';
import { VersioningAPI } from '../versioning';
import { BillingAPI } from '../billing';
import { SearchAPI } from '../search';
import { ObservabilityAPI } from '../observability';
import { GDPRAPI } from '../gdpr';
import { TenantsAPI } from '../tenants';
import { TransformationAPI } from '../transformation';
import { SemanticAPI } from '../semantic';
import { DatasetsAPI } from '../datasets';
import { AssetsAPI } from '../assets';
import { FilesAPI } from '../files';
import { DQAPI } from '../dq';
import { WorkflowsAPI } from '../workflows';
import * as errorClasses from '../errors';
import * as sdk from '../index';

describe('Phase 118G — JS SDK Full Parity', () => {
  describe('New modules importable', () => {
    it('GovernanceAPI', () => {
      expect(GovernanceAPI).not.toBeUndefined();
    });
    it('MeshAPI', () => {
      expect(MeshAPI).not.toBeUndefined();
    });
    it('VirtualizationAPI', () => {
      expect(VirtualizationAPI).not.toBeUndefined();
    });
    it('WebhooksAPI', () => {
      expect(WebhooksAPI).not.toBeUndefined();
    });
    it('MarketplaceAPI', () => {
      expect(MarketplaceAPI).not.toBeUndefined();
    });
    it('BaaSAPI', () => {
      expect(BaaSAPI).not.toBeUndefined();
    });
    it('MLAPI', () => {
      expect(MLAPI).not.toBeUndefined();
    });
    it('ScheduledIngestionAPI', () => {
      expect(ScheduledIngestionAPI).not.toBeUndefined();
    });
    it('ScheduledExportAPI', () => {
      expect(ScheduledExportAPI).not.toBeUndefined();
    });
    it('VersioningAPI', () => {
      expect(VersioningAPI).not.toBeUndefined();
    });
    it('BillingAPI', () => {
      expect(BillingAPI).not.toBeUndefined();
    });
    it('SearchAPI', () => {
      expect(SearchAPI).not.toBeUndefined();
    });
    it('ObservabilityAPI', () => {
      expect(ObservabilityAPI).not.toBeUndefined();
    });
    it('GDPRAPI', () => {
      expect(GDPRAPI).not.toBeUndefined();
    });
    it('TenantsAPI', () => {
      expect(TenantsAPI).not.toBeUndefined();
    });
    it('TransformationAPI', () => {
      expect(TransformationAPI).not.toBeUndefined();
    });
    it('SemanticAPI', () => {
      expect(SemanticAPI).not.toBeUndefined();
    });
    it('DatasetsAPI', () => {
      expect(DatasetsAPI).not.toBeUndefined();
    });
    it('AssetsAPI', () => {
      expect(AssetsAPI).not.toBeUndefined();
    });
    it('FilesAPI', () => {
      expect(FilesAPI).not.toBeUndefined();
    });
    it('DQAPI', () => {
      expect(DQAPI).not.toBeUndefined();
    });
    it('WorkflowsAPI', () => {
      expect(WorkflowsAPI).not.toBeUndefined();
    });
  });

  describe('Error classes', () => {
    const {
      BillingError,
      BillingValidationError,
      DowngradeLimitExceededError,
      DataHubError,
      SemanticError,
      SPARQLError,
      SHACLValidationError,
      EntitlementRequiredError,
      CircuitBreakerOpenError,
      ServerError,
    } = errorClasses;

    it('BillingError hierarchy', () => {
      const e1 = new BillingError('test');
      expect(e1).toBeInstanceOf(DataHubError);
      expect(e1.code).toBe('BILLING_ERROR');

      const e2 = new BillingValidationError('test');
      expect(e2).toBeInstanceOf(BillingError);

      const e3 = new DowngradeLimitExceededError('test');
      expect(e3).toBeInstanceOf(BillingError);
    });

    it('Semantic error hierarchy', () => {
      expect(new SPARQLError('test')).toBeInstanceOf(SemanticError);
      expect(new SHACLValidationError('test')).toBeInstanceOf(SemanticError);
    });

    it('EntitlementRequiredError has 403 status', () => {
      const e = new EntitlementRequiredError();
      expect(e).toBeInstanceOf(DataHubError);
      expect(e.code).toBe('ENTITLEMENT_REQUIRED');
      expect(e.httpStatus).toBe(403);
    });

    it('CircuitBreakerOpenError is 503', () => {
      const e = new CircuitBreakerOpenError();
      expect(e).toBeInstanceOf(ServerError);
      expect(e.httpStatus).toBe(503);
    });

    it('All 30 domain error classes exist', () => {
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
        expect((errorClasses as any)[name]).not.toBeUndefined();
      }
    });
  });

  describe('Client mounts all modules', () => {
    it('all 25 modules are mounted', () => {
      const client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'test-token',
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
        expect((sdk as any)[name]).not.toBeUndefined();
      }
    });
  });
});
