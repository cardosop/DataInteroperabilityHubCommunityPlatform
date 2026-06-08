/**
 * Phase 278.H.4 — Saved searches API service.
 */
import { apiClient } from '../../../shared/api/client';
import type {
  SavedSearch,
  SavedSearchCreateRequest,
  SavedSearchUpdateRequest,
} from '../../../shared/types/marketplace';

const BASE = 'marketplace/saved-searches';

export const savedSearchService = {
  async list(): Promise<SavedSearch[]> {
    const response = await apiClient.getClient().get<SavedSearch[]>(`${BASE}/`);
    return response.data;
  },

  async get(id: string): Promise<SavedSearch> {
    const response = await apiClient.getClient().get<SavedSearch>(`${BASE}/${id}/`);
    return response.data;
  },

  async create(data: SavedSearchCreateRequest): Promise<SavedSearch> {
    const response = await apiClient.getClient().post<SavedSearch>(`${BASE}/`, data);
    return response.data;
  },

  async update(id: string, data: SavedSearchUpdateRequest): Promise<SavedSearch> {
    const response = await apiClient.getClient().patch<SavedSearch>(`${BASE}/${id}/`, data);
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${BASE}/${id}/`);
  },
};
