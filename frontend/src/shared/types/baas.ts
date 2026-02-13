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
}

export interface APIKeyCreateRequest {
  name: string;
  tier?: APITier;
  expires_at?: string;
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
