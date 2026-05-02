/**
 * Search (Full-Text) Service
 * Calls GET /api/v1/search/search/ with query and filters.
 *
 * Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) extends the same endpoint
 * with the ``?semantic=true`` query parameter — when set AND the
 * tenant has ``semantic_search_enabled=True``, the backend expands
 * the query via tenant-active ontologies (skos:altLabel /
 * skos:related / owl:equivalentClass / rdfs:subClassOf ancestors at
 * depth ≤ 2) and tags expansion-only matches with
 * ``matched_via=ontology`` + ``bridge_term=<label>``.
 */

import { apiClient } from '../../../shared/api/client';
import type { SearchResponse, SearchFilters } from '../../../shared/types/search';

const SEARCH_BASE_PATH = 'search/search';

export const searchService = {
  /**
   * Full-text search across assets, contracts, and datasets.
   * GET /api/v1/search/search/?q=...&type=...&semantic=true&...
   *
   * Setting ``filters.semantic = true`` forwards ``semantic=true`` on
   * the same endpoint — no separate URL.  The backend gates the
   * actual expansion on ``Tenant.semantic_search_enabled``; if the
   * tenant flag is False the param is a no-op (legacy semantics
   * preserved per the spec scenario "Toggle off reproduces today's
   * behaviour").
   */
  async search(query: string, filters: SearchFilters = {}): Promise<SearchResponse> {
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    if (filters.type) params.set('type', filters.type);
    if (filters.classification) params.set('classification', filters.classification);
    if (filters.owner) params.set('owner', filters.owner);
    if (filters.tags?.length) params.set('tags', filters.tags.join(','));
    if (filters.domain) params.set('domain', filters.domain);
    if (filters.quality_status) params.set('quality_status', filters.quality_status);
    if (filters.compliance_status) params.set('compliance_status', filters.compliance_status);
    if (filters.limit != null) params.set('limit', String(filters.limit));
    if (filters.offset != null) params.set('offset', String(filters.offset));
    if (filters.sort_by) params.set('sort_by', filters.sort_by);
    if (filters.sort_order) params.set('sort_order', filters.sort_order);
    if (filters.semantic) params.set('semantic', 'true');

    const queryString = params.toString();
    const url = queryString ? `${SEARCH_BASE_PATH}/?${queryString}` : `${SEARCH_BASE_PATH}/`;
    const response = await apiClient.getClient().get<SearchResponse>(url);
    return response.data;
  },
};
