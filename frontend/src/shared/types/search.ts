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
  /**
   * Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — set to "ontology" when
   * the result was matched via an ontology-aware bridge term rather
   * than the user's literal query.  Only present on expansion-only
   * matches; exact matches do NOT carry this field.
   */
  matched_via?: 'ontology';
  /**
   * Phase 230.11 — when ``matched_via=ontology``, the bridge term that
   * surfaced this result (e.g. user searched "customer", we matched
   * via "client" because of `Customer owl:equivalentClass Client`).
   */
  bridge_term?: string;
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
  /**
   * Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — when True, the search
   * runs against the unified search endpoint with ontology-aware
   * query expansion. Requires the tenant flag
   * ``semantic_search_enabled=True`` to actually expand; otherwise the
   * request runs as a normal FTS query.
   */
  semantic?: boolean;
}
