/**
 * Webhook types
 * Aligned with backend WebhookSerializer and Webhook model
 * Secret is write-only; not present on list/detail response
 */

export const WebhookStatus = {
  ACTIVE: 'ACTIVE',
  PAUSED: 'PAUSED',
  DISABLED: 'DISABLED',
} as const;
export type WebhookStatus = (typeof WebhookStatus)[keyof typeof WebhookStatus];

export const DeliveryStatus = {
  PENDING: 'PENDING',
  SUCCESS: 'SUCCESS',
  FAILED: 'FAILED',
  DEAD_LETTER: 'DEAD_LETTER',
  RATE_LIMITED: 'RATE_LIMITED',
} as const;
export type DeliveryStatus = (typeof DeliveryStatus)[keyof typeof DeliveryStatus];

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  webhook_name: string;
  webhook_url: string;
  event_type: string;
  payload: Record<string, unknown>;
  signature: string | null;
  signing_key_uuid?: string | null;
  status: DeliveryStatus;
  attempt_number: number;
  http_status_code: number | null;
  response_body: string | null;
  error_message: string | null;
  delivered_at: string | null;
  next_retry_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Webhook {
  id: string;
  name: string;
  url: string;
  event_types: string[];
  status: WebhookStatus;
  max_retries: number;
  retry_intervals: number[];
  created_at: string;
  updated_at: string;
}

export interface WebhookCreateRequest {
  name: string;
  url: string;
  secret: string;
  event_types: string[];
  status?: WebhookStatus;
  max_retries?: number;
  retry_intervals?: number[];
}

export interface WebhookUpdateRequest {
  name?: string;
  url?: string;
  secret?: string;
  event_types?: string[];
  status?: WebhookStatus;
  max_retries?: number;
  retry_intervals?: number[];
}

export interface WebhookListFilters {
  page?: number;
  page_size?: number;
}

export interface WebhookEventTypeOption {
  value: string;
  label: string;
}

export interface WebhookEventTypesResponse {
  event_types: WebhookEventTypeOption[];
  odps_event_types: string[];
}
