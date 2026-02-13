/**
 * AI Service
 * API client for AI-powered operations
 */

import { apiClient } from '../../../shared/api/client';
import type {
  NaturalLanguageSearchRequest,
  NaturalLanguageSearchResponse,
  SchemaMatchingRequest,
  SchemaMatchingResponse,
} from '../../../shared/types/ai';

const AI_BASE_PATH = 'ai';

export const aiService = {
  /**
   * Execute natural language search
   */
  async naturalLanguageSearch(data: NaturalLanguageSearchRequest): Promise<NaturalLanguageSearchResponse> {
    const response = await apiClient.getClient().post<NaturalLanguageSearchResponse>(
      `${AI_BASE_PATH}/natural-language-search/`,
      data
    );
    return response.data;
  },

  /**
   * Execute schema matching
   */
  async schemaMatching(data: SchemaMatchingRequest): Promise<SchemaMatchingResponse> {
    const response = await apiClient.getClient().post<SchemaMatchingResponse>(
      `${AI_BASE_PATH}/schema-matching/`,
      data
    );
    return response.data;
  },
};
