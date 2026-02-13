/**
 * Semantic Types
 * Aligned with backend semantic endpoints
 */

export type SPARQLOutputFormat = 'json' | 'csv' | 'turtle' | 'xml';

export type SemanticResourceType = 'ASSET' | 'CONTRACT' | 'DATASET' | 'FIELD';

export type SemanticResourceStatus = 'ACTIVE' | 'PENDING' | 'ERROR';

export interface SPARQLQueryRequest {
  query: string;
  format?: SPARQLOutputFormat;
  timeout?: number;
}

export interface SPARQLQueryResponse {
  results: Record<string, unknown>;
  format: string;
  truncated: boolean;
  warning?: string;
}

export interface URIResolutionResponse {
  '@context': Record<string, unknown>;
  '@id': string;
  '@type': string;
  uri: string;
  [key: string]: unknown;
}

export interface SemanticResource {
  id: string;
  tenant: string;
  resource_type: SemanticResourceType;
  resource_id: string;
  uri: string;
  status: SemanticResourceStatus;
  last_mapped_at: string | null;
  mapping_version: number;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface SemanticResourceListFilters {
  page?: number;
  page_size?: number;
}

export interface SemanticResourceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: SemanticResource[];
}
