/**
 * Interoperable Data Hub JavaScript SDK
 *
 * TypeScript/JavaScript client library for the Interoperable Data Hub API.
 * Generated from OpenAPI spec with custom authentication and error handling.
 */

export { DataHubClient } from './client';
export type { DataHubClientConfig } from './config';
export { DEFAULT_CONFIG } from './config';
export * from './errors';
export * from './types';
export { camelToSnake, snakeToCamel, camelToSnakeKey, snakeToCamelKey } from './caseTransform';

// API modules
export { ContractsAPI } from './contracts';
export { LineageAPI } from './lineage';
export { ComplianceAPI } from './compliance';
export { GovernanceAPI } from './governance';
export { MeshAPI } from './mesh';
export { VirtualizationAPI } from './virtualization';
export { WebhooksAPI } from './webhooks';
export { MarketplaceAPI } from './marketplace';
export { BaaSAPI } from './baas';
export { MLAPI } from './ml';
export { ScheduledIngestionAPI } from './scheduledIngestion';
export { ScheduledExportAPI } from './scheduledExport';
export { VersioningAPI } from './versioning';
export { BillingAPI } from './billing';
export { SearchAPI } from './search';
export { ObservabilityAPI } from './observability';
export { GDPRAPI } from './gdpr';
export { TenantsAPI } from './tenants';
export { TransformationAPI } from './transformation';
export { SemanticAPI } from './semantic';
export { DatasetsAPI } from './datasets';
export { AssetsAPI } from './assets';
export { FilesAPI } from './files';
export { DQAPI } from './dq';
export { WorkflowsAPI } from './workflows';

export type {
  CreateComplianceRunParams,
  ListComplianceRunsParams,
  ComplianceRun,
  ComplianceRunResults,
  ScanMode,
  ComplianceRunStatus,
  RiskLevel,
} from './compliance';

// Re-export generated API clients
export * from './generated';

