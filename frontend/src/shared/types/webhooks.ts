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
