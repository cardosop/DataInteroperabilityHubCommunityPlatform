/**
 * Marketplace Types
 * Based on backend marketplace serializers and models
 */

export const ListingStatus = {
  DRAFT: 'DRAFT',
  PUBLISHED: 'PUBLISHED',
  UNLISTED: 'UNLISTED',
  DELETED: 'DELETED',
} as const;

export type ListingStatus = typeof ListingStatus[keyof typeof ListingStatus];

export const PricingModel = {
  FREE: 'FREE',
  FREE_AUTO_APPROVE: 'FREE_AUTO_APPROVE',
  REQUEST_APPROVAL: 'REQUEST_APPROVAL',
} as const;

export type PricingModel = typeof PricingModel[keyof typeof PricingModel];

export interface Listing {
  id: string;
  tenant: string;
  asset: string;
  status: ListingStatus;
  pricing_model: PricingModel;
  metadata_json?: Record<string, unknown> | null;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
  // Read-only computed fields
  title?: string;
  description?: string;
  short_description?: string;
  long_description?: string;
  price_amount?: string;
  currency?: string;
  tags?: string[] | string;
  domain?: string;
}

export interface ListingCreateRequest {
  asset_id: string;
  title: string;
  short_description: string; // Required by API
  long_description?: string; // Optional detailed description
  description?: string; // Deprecated - use short_description instead
  license_summary?: string;
  intended_use?: string[];
  restricted_use?: string[];
  pricing_model?: PricingModel;
  price_amount?: number;
  currency?: string;
  tags?: string[];
  domain?: string;
  metadata_json?: Record<string, unknown>;
}

export interface ListingUpdateRequest {
  title?: string;
  description?: string;
  license_summary?: string;
  intended_use?: string[];
  restricted_use?: string[];
  pricing_model?: PricingModel;
  status?: ListingStatus;
  metadata_json?: Record<string, unknown>;
}

export interface ListingListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  domain?: string;
  pricing_model?: PricingModel;
  status?: ListingStatus;
}

export const OrderStatus = {
  REQUESTED: 'REQUESTED',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  CANCELLED: 'CANCELLED',
  FULFILLED: 'FULFILLED',
} as const;

export type OrderStatus = typeof OrderStatus[keyof typeof OrderStatus];

export interface Order {
  id: string;
  tenant: string;
  listing: string;
  status: OrderStatus;
  created_by?: string | null;
  approved_by?: string | null;
  metadata_json?: Record<string, unknown> | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  fulfilled_at?: string | null;
  created_at: string;
  updated_at: string;
  // Read-only computed fields
  listing_title?: string;
  asset_id?: string;
  rejection_reason?: string;
}

export interface OrderCreateRequest {
  listing_id: string;
  purpose?: string;
  metadata_json?: Record<string, unknown>;
}

export interface OrderListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  status?: OrderStatus;
  listing_id?: string;
}

export const EntitlementStatus = {
  ACTIVE: 'ACTIVE',
  REVOKED: 'REVOKED',
  EXPIRED: 'EXPIRED',
} as const;

export type EntitlementStatus = typeof EntitlementStatus[keyof typeof EntitlementStatus];

export interface Entitlement {
  id: string;
  tenant: string;
  listing: string;
  asset: string;
  order?: string | null;
  status: EntitlementStatus;
  granted_at: string;
  revoked_at?: string | null;
  expires_at?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  // Read-only computed fields
  asset_name?: string;
  listing_title?: string;
  is_active?: string;
}

export interface EntitlementListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  status?: EntitlementStatus;
  listing_id?: string;
  asset_id?: string;
}

export interface CheckAccessRequest {
  asset_id: string;
}

export interface CheckAccessResponse {
  has_access: boolean;
  entitlement_id?: string | null;
  reason?: string;
}
