/**
 * Search (Full-Text) Service
 * Phase 273.1 — canonical endpoint: GET /api/search/?q=&types=
 *
 * Formerly called the deprecated /api/v1/search/search/ ViewSet.
 * The canonical UnifiedSearchView handles FTS via PostgreSQL
 * search_vector on Asset + Contract models with optional semantic
 * query expansion (Phase 230.11).
 */

import { apiClient } from '../../../shared/api/client';
import type { SearchResponse, SearchFilters } from '../../../shared/types/search';

const SEARCH_BASE_PATH = 'search';

/** Map the frontend Scope enum to canonical ``types`` values. */
const SCOPE_TO_TYPES: Record<string, string> = {
  ALL: 'assets,contracts',
  ASSET: 'assets',
  CONTRACT: 'contracts',
  DATASET: 'assets,contracts',
};

export const searchService = {
  async search(query: string, filters: SearchFilters = {}): Promise<SearchResponse> {
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());

    // Canonical endpoint uses ``types`` (comma-separated, lowercase).
    const types = SCOPE_TO_TYPES[filters.type || 'ALL'] || 'assets,contracts';
    params.set('types', types);

    if (filters.tags?.length) params.set('tags', filters.tags.join(','));
    if (filters.semantic) params.set('semantic', 'true');

    const queryString = params.toString();
    const url = queryString ? `${SEARCH_BASE_PATH}/?${queryString}` : `${SEARCH_BASE_PATH}/`;
    const response = await apiClient.getClient().get<SearchResponse>(url);
    return response.data;
  },
};
