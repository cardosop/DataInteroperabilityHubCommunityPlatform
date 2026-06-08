/**
 * Phase 278.H.1 — Recommendations React Query hooks.
 */
import { useQuery, useMutation } from '@tanstack/react-query';
import { recommendationsService } from '../services/recommendationsService';
import type { RecommendationsParams } from '../services/recommendationsService';

export function useRecommendations(params: RecommendationsParams = {}) {
  return useQuery({
    queryKey: ['marketplace', 'recommendations', params],
    queryFn: () => recommendationsService.getRecommendations(params),
    staleTime: 5 * 60 * 1000, // 5 min — recommendations are stable
    retry: 1,
  });
}

export function useSubmitRecommendationFeedback() {
  return useMutation({
    mutationFn: ({
      listingId,
      helpful,
      reason,
    }: {
      listingId: string;
      helpful: boolean;
      reason?: string;
    }) => recommendationsService.submitFeedback(listingId, helpful, reason),
  });
}
