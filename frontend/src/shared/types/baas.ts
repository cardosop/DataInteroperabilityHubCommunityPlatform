/**
 * BaaS Platform Types
 * Based on backend BaaS models and serializers
 */

export const APITier = {
  FREE: 'FREE',
  PRO: 'PRO',
  ENTERPRISE: 'ENTERPRISE',
} as const;
export type APITier = (typeof APITier)[keyof typeof APITier];

export interface APIKey {
  id: string;
  name: string;
  tier: APITier;
  expires_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
  updated_at: string;
  // Only returned on creation
  key?: string;
  // Customer billing fields (Phase 116A.1 / 116C)
  customer_id?: string | null;
  customer_name?: string | null;
  customer_email?: string | null;
  customer_metadata?: Record<string, unknown>;
}

export interface APIKeyCreateRequest {
  name: string;
  tier?: APITier;
  expires_at?: string;
  /** Customer billing fields (Phase 116C) */
  customer_id?: string;
  customer_name?: string;
  customer_email?: string;
  pricing?: {
    monthly_flat_fee: string;
    included_requests: number;
    overage_rate: string;
  };
}

export interface APIKeyUpdateRequest {
  name?: string;
  tier?: APITier;
  expires_at?: string;
}

export interface UsageStats {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate: number;
  average_response_time_ms: number;
  period_start: string;
  period_end: string;
}

export interface UsageByEndpoint {
  endpoint: string;
  requests: number;
  successful: number;
  failed: number;
  average_response_time_ms: number;
}

export interface UsageByTenant {
  tenant_id: string;
  tenant_name?: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
}

export interface UsageFilters {
  api_key_id?: string;
  start_date?: string;
  end_date?: string;
}

// --- Phase 116C: Customer Billing Types ---

export const BillingReportStatus = {
  DRAFT: 'DRAFT',
  FINALIZED: 'FINALIZED',
  SENT: 'SENT',
  VOID: 'VOID',
} as const;
export type BillingReportStatus = (typeof BillingReportStatus)[keyof typeof BillingReportStatus];

export interface CustomerBillingReport {
  id: string;
  tenant_id: string;
  api_key_id: string | null;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  period_start: string;
  period_end: string;
  total_requests: number;
  billable_requests: number;
  included_requests: number;
  overage_requests: number;
  base_fee: string;
  overage_fee: string;
  total_amount: string;
  currency: string;
  status: BillingReportStatus;
  finalized_at: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BillingReportGenerateRequest {
  api_key_id: string;
  period_start: string;
  period_end: string;
}

export interface APIKeyPricing {
  id: string;
  price_per_request: string;
  monthly_flat_fee: string;
  overage_rate: string;
  included_requests: number;
  currency: string;
  created_at: string;
  updated_at: string;
}

export interface CustomerSummary {
  customer_id: string;
  customer_name: string;
  customer_email: string;
  api_key_count: number;
  total_requests: number;
  total_billed: string;
  currency: string;
}
