/**
 * Phase 278.H.1 — Recommendations React Query hooks.
 */
import { useQuery } from '@tanstack/react-query';
import { recommendationsService } from '../services/recommendationsService';
import type { RecommendationsParams } from '../services/recommendationsService';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { getErrorMessage } from '../../../shared/utils/errorUtils';

export function useRecommendations(params: RecommendationsParams = {}) {
  return useQuery({
    queryKey: ['marketplace', 'recommendations', params],
    queryFn: () => recommendationsService.getRecommendations(params),
    staleTime: 5 * 60 * 1000, // 5 min — recommendations are stable
    retry: 1,
  });
}

export function useSubmitRecommendationFeedback() {
  // W5.4 (MEDIUM-8) — feedback submission failures were silent (plain
  // useMutation, no onError); the notification wrapper fires an assertive
  // error toast.
  return useMutationWithNotification({
    mutationFn: ({
      listingId,
      helpful,
      reason,
    }: {
      listingId: string;
      helpful: boolean;
      reason?: string;
    }) => recommendationsService.submitFeedback(listingId, helpful, reason),
    errorMessage: (error) =>
      `Couldn't submit feedback: ${getErrorMessage(error)}`,
  });
}
