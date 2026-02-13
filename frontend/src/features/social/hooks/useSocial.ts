/**
 * Social Features React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { socialService } from '../services/socialService';
import type {
  RatingCreateRequest,
  ReviewCreateRequest,
  CommentCreateRequest,
  CommunityCreateRequest,
  CommunityJoinRequest,
  SocialListFilters,
} from '../../../shared/types/social';

export function useRatings(assetId: string, filters: SocialListFilters = {}) {
  return useQuery({
    queryKey: ['social', 'ratings', assetId, filters],
    queryFn: () => socialService.getRatings(assetId, filters),
    enabled: !!assetId,
  });
}

export function useSubmitRating() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RatingCreateRequest) => socialService.submitRating(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['social', 'ratings', variables.asset_id] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.asset_id] });
    },
  });
}

export function useReviews(assetId: string, filters: SocialListFilters = {}) {
  return useQuery({
    queryKey: ['social', 'reviews', assetId, filters],
    queryFn: () => socialService.getReviews(assetId, filters),
    enabled: !!assetId,
  });
}

export function useReview(id: string | null) {
  return useQuery({
    queryKey: ['social', 'reviews', 'detail', id],
    queryFn: () => socialService.getReview(id!),
    enabled: !!id,
  });
}

export function useSubmitReview() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ReviewCreateRequest) => socialService.submitReview(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['social', 'reviews', variables.asset_id] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.asset_id] });
    },
  });
}

export function useComments(assetId: string, filters: SocialListFilters = {}) {
  return useQuery({
    queryKey: ['social', 'comments', assetId, filters],
    queryFn: () => socialService.getComments(assetId, filters),
    enabled: !!assetId,
  });
}

export function useComment(id: string | null) {
  return useQuery({
    queryKey: ['social', 'comments', 'detail', id],
    queryFn: () => socialService.getComment(id!),
    enabled: !!id,
  });
}

export function useSubmitComment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CommentCreateRequest) => socialService.submitComment(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['social', 'comments', variables.asset_id] });
      queryClient.invalidateQueries({ queryKey: ['assets', 'detail', variables.asset_id] });
    },
  });
}

export function useCommunities(filters: SocialListFilters = {}) {
  return useQuery({
    queryKey: ['social', 'communities', filters],
    queryFn: () => socialService.listCommunities(filters),
  });
}

export function useCommunity(id: string | null) {
  return useQuery({
    queryKey: ['social', 'communities', 'detail', id],
    queryFn: () => socialService.getCommunity(id!),
    enabled: !!id,
  });
}

export function useCreateOrJoinCommunity() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CommunityCreateRequest | CommunityJoinRequest) =>
      socialService.createOrJoinCommunity(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social', 'communities'] });
    },
  });
}

export function useCommunityMembers(communityId: string, filters: SocialListFilters = {}) {
  return useQuery({
    queryKey: ['social', 'communities', communityId, 'members', filters],
    queryFn: () => socialService.getCommunityMembers(communityId, filters),
    enabled: !!communityId,
  });
}
