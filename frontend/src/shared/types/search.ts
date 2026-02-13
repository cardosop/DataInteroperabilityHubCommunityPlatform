/**
 * Search (Full-Text) Types
 * Aligned with backend GET /api/v1/search/search/ response and query params
 */

export type SearchResultType = 'CONTRACT' | 'ASSET' | 'DATASET';

export interface SearchResult {
  id: string;
  type: SearchResultType;
  title: string;
  description: string | null;
  relevance_score: number;
  classification: string | null;
  owner_id: string | null;
  owner_email: string | null;
  domain: string | null;
  tags: string[];
  quality_status: string | null;
  compliance_status: string | null;
  indexed_at: string | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  limit: number;
  offset: number;
  query: string;
  analytics_id?: string | null;
}

export interface SearchFilters {
  type?: SearchResultType;
  classification?: string;
  owner?: string;
  tags?: string[];
  domain?: string;
  quality_status?: string;
  compliance_status?: string;
  limit?: number;
  offset?: number;
  sort_by?: 'relevance' | 'created_at' | 'indexed_at';
  sort_order?: 'asc' | 'desc';
}
