/**
 * Developer Service
 * API client for developer portal operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type { Plugin, SDKDocumentation, DeveloperListFilters } from '../../../shared/types/developer';

const DEVELOPER_BASE_PATH = 'developer';

export const developerService = {
  /**
   * List plugins
   */
  async listPlugins(filters: DeveloperListFilters = {}): Promise<PaginatedResponse<Plugin>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.category) params.append('category', filters.category);
    if (filters.status) params.append('status', filters.status);
    if (filters.search) params.append('search', filters.search);
    if (filters.sort) params.append('sort', filters.sort);

    const response = await apiClient.getClient().get<PaginatedResponse<Plugin>>(
      `${DEVELOPER_BASE_PATH}/plugins/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get plugin by ID
   */
  async getPlugin(id: string): Promise<Plugin> {
    const response = await apiClient.getClient().get<Plugin>(`${DEVELOPER_BASE_PATH}/plugins/${id}/`);
    return response.data;
  },

  /**
   * List SDK documentation
   */
  async listSDKDocumentation(filters: DeveloperListFilters = {}): Promise<PaginatedResponse<SDKDocumentation>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.language) params.append('language', filters.language);

    const response = await apiClient.getClient().get<PaginatedResponse<SDKDocumentation>>(
      `${DEVELOPER_BASE_PATH}/sdk/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get SDK documentation by ID
   */
  async getSDKDocumentation(id: string): Promise<SDKDocumentation> {
    const response = await apiClient.getClient().get<SDKDocumentation>(`${DEVELOPER_BASE_PATH}/sdk/${id}/`);
    return response.data;
  },
};
