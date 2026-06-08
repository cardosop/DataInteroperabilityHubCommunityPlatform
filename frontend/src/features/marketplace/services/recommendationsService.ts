/**
 * Phase 278.H.1 — Recommendations API service.
 *
 * Consumes the /ai/recommendations/ endpoint (wired to real
 * MarketplaceRecommendationService on the backend).
 */
import { apiClient } from '../../../shared/api/client';
import type { MarketplaceRecommendations } from '../../../shared/types/marketplace';

const RECOMMENDATIONS_PATH = 'ai/recommendations';

export interface RecommendationsParams {
  domain?: string;
  listing_id?: string;
  limit?: number;
}

export const recommendationsService = {
  async getRecommendations(
    params: RecommendationsParams = {},
  ): Promise<MarketplaceRecommendations> {
    const searchParams = new URLSearchParams();
    if (params.domain) searchParams.append('domain', params.domain);
    if (params.listing_id) searchParams.append('listing_id', params.listing_id);
    if (params.limit) searchParams.append('limit', String(params.limit));

    const qs = searchParams.toString();
    const url = qs
      ? `${RECOMMENDATIONS_PATH}/?${qs}`
      : `${RECOMMENDATIONS_PATH}/`;

    const response = await apiClient
      .getClient()
      .get<MarketplaceRecommendations>(url);
    return response.data;
  },

  async submitFeedback(
    listingId: string,
    helpful: boolean,
    reason?: string,
  ): Promise<void> {
    await apiClient
      .getClient()
      .post(`${RECOMMENDATIONS_PATH}/feedback/`, {
        listing_id: listingId,
        helpful,
        reason: reason || '',
      });
  },
};
