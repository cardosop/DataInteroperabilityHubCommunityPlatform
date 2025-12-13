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
export { ContractsAPI } from './contracts';
export { LineageAPI } from './lineage';

// Re-export generated API clients
export * from './generated';

