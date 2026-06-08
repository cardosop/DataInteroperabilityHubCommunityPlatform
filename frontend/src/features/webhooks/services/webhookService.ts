/**
 * Webhook Service
 * API client for webhook CRUD (real API; no mocks)
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Webhook,
  WebhookCreateRequest,
  WebhookDelivery,
  WebhookEventTypesResponse,
  WebhookListFilters,
  WebhookUpdateRequest,
} from '../../../shared/types/webhooks';

const WEBHOOKS_BASE_PATH = 'webhooks/webhooks';

function normalizePagination<T>(
  data: PaginatedResponse<T> & { next?: string | null; previous?: string | null }
): PaginatedResponse<T> {
  if (typeof data.has_next === 'boolean') return data as PaginatedResponse<T>;
  return {
    ...data,
    has_next: !!data.next,
    has_previous: !!data.previous,
    next_page: data.next != null ? data.page + 1 : null,
    previous_page: data.previous != null ? data.page - 1 : null,
  } as PaginatedResponse<T>;
}

export const webhookService = {
  async list(filters: WebhookListFilters = {}): Promise<PaginatedResponse<Webhook>> {
    const params = new URLSearchParams();
    if (filters.page != null) params.set('page', String(filters.page));
    if (filters.page_size != null) params.set('page_size', String(filters.page_size));
    const url = params.toString()
      ? `${WEBHOOKS_BASE_PATH}/?${params.toString()}`
      : `${WEBHOOKS_BASE_PATH}/`;
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<Webhook> & { next?: string; previous?: string }>(url);
    return normalizePagination(response.data);
  },

  async getById(id: string): Promise<Webhook> {
    const response = await apiClient.getClient().get<Webhook>(`${WEBHOOKS_BASE_PATH}/${id}/`);
    return response.data;
  },

  async create(data: WebhookCreateRequest): Promise<Webhook> {
    const response = await apiClient.getClient().post<Webhook>(`${WEBHOOKS_BASE_PATH}/`, data);
    return response.data;
  },

  async update(id: string, data: WebhookUpdateRequest): Promise<Webhook> {
    const response = await apiClient.getClient().put<Webhook>(`${WEBHOOKS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  async patch(id: string, data: Partial<WebhookUpdateRequest>): Promise<Webhook> {
    const response = await apiClient
      .getClient()
      .patch<Webhook>(`${WEBHOOKS_BASE_PATH}/${id}/`, data);
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.getClient().delete(`${WEBHOOKS_BASE_PATH}/${id}/`);
  },

  async getEventTypes(odpsOnly = false): Promise<WebhookEventTypesResponse> {
    const url = odpsOnly
      ? `${WEBHOOKS_BASE_PATH}/event-types/?odps_only=true`
      : `${WEBHOOKS_BASE_PATH}/event-types/`;
    const response = await apiClient.getClient().get<WebhookEventTypesResponse>(url);
    return response.data;
  },

  async test(id: string): Promise<{ status: string }> {
    const response = await apiClient
      .getClient()
      .post<{ status: string }>(`${WEBHOOKS_BASE_PATH}/${id}/test/`);
    return response.data;
  },

  async getDeliveries(
    webhookId: string,
    params?: { page?: number; page_size?: number; status?: string }
  ): Promise<PaginatedResponse<WebhookDelivery>> {
    const response = await apiClient
      .getClient()
      .get<PaginatedResponse<WebhookDelivery> & { next?: string; previous?: string }>(
        `${WEBHOOKS_BASE_PATH}/${webhookId}/deliveries/`,
        { params }
      );
    return normalizePagination(response.data);
  },

  async retryDelivery(deliveryId: string): Promise<{ status: string }> {
    const response = await apiClient
      .getClient()
      .post<{ status: string }>(`webhooks/webhook-deliveries/${deliveryId}/retry/`);
    return response.data;
  },
};
