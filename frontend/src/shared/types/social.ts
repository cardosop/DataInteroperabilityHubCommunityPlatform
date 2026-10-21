/**
 * Social Features Types
 * Based on backend Social serializers and models
 */

export const ReviewStatus = {
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
} as const;
export type ReviewStatus = (typeof ReviewStatus)[keyof typeof ReviewStatus];

export const CommentStatus = {
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
} as const;
export type CommentStatus = (typeof CommentStatus)[keyof typeof CommentStatus];

export interface Rating {
  id: string;
  asset_id: string;
  user_id: string;
  rating: number; // 1-5
  comment?: string;
  created_at: string;
  updated_at: string;
}

export interface RatingCreateRequest {
  asset_id: string;
  rating: number; // 1-5
  comment?: string;
}

export interface Review {
  id: string;
  asset_id: string;
  user_id: string;
  review_text: string;
  rating?: number; // 1-5, optional
  status: ReviewStatus;
  helpful_count: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewCreateRequest {
  asset_id: string;
  review_text: string;
  rating?: number; // 1-5, optional
}

export interface Comment {
  id: string;
  asset_id: string;
  user_id: string;
  parent_comment_id?: string;
  comment_text: string;
  status: CommentStatus;
  mentions: string[];
  created_at: string;
  updated_at: string;
  // Nested comments (populated in detail view)
  replies?: Comment[];
}

export interface CommentCreateRequest {
  asset_id: string;
  comment_text: string;
  parent_comment_id?: string;
}

export interface Community {
  id: string;
  name: string;
  description?: string;
  is_public: boolean;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface CommunityCreateRequest {
  name: string;
  description?: string;
  is_public?: boolean;
}

export interface CommunityMember {
  id: string;
  community_id: string;
  user_id: string;
  joined_at: string;
}

export interface CommunityJoinRequest {
  community_id: string;
}

export interface SocialListFilters {
  page?: number;
  page_size?: number;
  asset_id?: string;
  user_id?: string;
  status?: ReviewStatus | CommentStatus;
}
