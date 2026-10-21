/**
 * Social Service
 * API client for social features operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Rating,
  RatingCreateRequest,
  Review,
  ReviewCreateRequest,
  Comment,
  CommentCreateRequest,
  Community,
  CommunityCreateRequest,
  CommunityMember,
  CommunityJoinRequest,
  SocialListFilters,
} from '../../../shared/types/social';

const SOCIAL_BASE_PATH = 'social';

export const socialService = {
  /**
   * Submit a rating for an asset
   */
  async submitRating(data: RatingCreateRequest): Promise<Rating> {
    const response = await apiClient.getClient().post<Rating>(`${SOCIAL_BASE_PATH}/ratings/`, data);
    return response.data;
  },

  /**
   * Get ratings for an asset
   */
  async getRatings(assetId: string, filters: SocialListFilters = {}): Promise<PaginatedResponse<Rating>> {
    const params = new URLSearchParams();
    params.append('asset_id', assetId);
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());

    const response = await apiClient.getClient().get<PaginatedResponse<Rating>>(
      `${SOCIAL_BASE_PATH}/ratings/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Submit a review for an asset
   */
  async submitReview(data: ReviewCreateRequest): Promise<Review> {
    const response = await apiClient.getClient().post<Review>(`${SOCIAL_BASE_PATH}/reviews/`, data);
    return response.data;
  },

  /**
   * Get reviews for an asset
   */
  async getReviews(assetId: string, filters: SocialListFilters = {}): Promise<PaginatedResponse<Review>> {
    const params = new URLSearchParams();
    params.append('asset_id', assetId);
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.status) params.append('status', filters.status);

    const response = await apiClient.getClient().get<PaginatedResponse<Review>>(
      `${SOCIAL_BASE_PATH}/reviews/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get review by ID
   */
  async getReview(id: string): Promise<Review> {
    const response = await apiClient.getClient().get<Review>(`${SOCIAL_BASE_PATH}/reviews/${id}/`);
    return response.data;
  },

  /**
   * Submit a comment for an asset
   */
  async submitComment(data: CommentCreateRequest): Promise<Comment> {
    const response = await apiClient.getClient().post<Comment>(`${SOCIAL_BASE_PATH}/comments/`, data);
    return response.data;
  },

  /**
   * Get comments for an asset
   */
  async getComments(assetId: string, filters: SocialListFilters & { parent_comment_id?: string } = {}): Promise<PaginatedResponse<Comment>> {
    const params = new URLSearchParams();
    params.append('asset_id', assetId);
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.status) params.append('status', filters.status);
    if ((filters as Record<string, unknown>).parent_comment_id) params.append('parent_comment_id', String((filters as Record<string, unknown>).parent_comment_id));

    const response = await apiClient.getClient().get<PaginatedResponse<Comment>>(
      `${SOCIAL_BASE_PATH}/comments/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get comment by ID
   */
  async getComment(id: string): Promise<Comment> {
    const response = await apiClient.getClient().get<Comment>(`${SOCIAL_BASE_PATH}/comments/${id}/`);
    return response.data;
  },

  /**
   * List communities
   */
  async listCommunities(filters: SocialListFilters = {}): Promise<PaginatedResponse<Community>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());

    const response = await apiClient.getClient().get<PaginatedResponse<Community>>(
      `${SOCIAL_BASE_PATH}/communities/?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get community by ID
   */
  async getCommunity(id: string): Promise<Community> {
    const response = await apiClient.getClient().get<Community>(`${SOCIAL_BASE_PATH}/communities/${id}/`);
    return response.data;
  },

  /**
   * Create or join a community
   */
  async createOrJoinCommunity(data: CommunityCreateRequest | CommunityJoinRequest): Promise<Community> {
    const response = await apiClient.getClient().post<Community>(`${SOCIAL_BASE_PATH}/communities/`, data);
    return response.data;
  },

  /**
   * Get community members
   */
  async getCommunityMembers(communityId: string, filters: SocialListFilters = {}): Promise<PaginatedResponse<CommunityMember>> {
    const params = new URLSearchParams();
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());

    const response = await apiClient.getClient().get<PaginatedResponse<CommunityMember>>(
      `${SOCIAL_BASE_PATH}/communities/${communityId}/members/?${params.toString()}`
    );
    return response.data;
  },
};
