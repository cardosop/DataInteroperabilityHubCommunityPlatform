/**
 * Search (Full-Text) Service
 * Calls GET /api/v1/search/search/ with query and filters
 */

import { apiClient } from '../../../shared/api/client';
import type { SearchResponse, SearchFilters } from '../../../shared/types/search';

const SEARCH_BASE_PATH = 'search/search';

export const searchService = {
  /**
   * Full-text search across assets, contracts, and datasets.
   * GET /api/v1/search/search/?q=...&type=...&...
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

    const queryString = params.toString();
    const url = queryString ? `${SEARCH_BASE_PATH}/?${queryString}` : `${SEARCH_BASE_PATH}/`;
    const response = await apiClient.getClient().get<SearchResponse>(url);
    return response.data;
  },
};
