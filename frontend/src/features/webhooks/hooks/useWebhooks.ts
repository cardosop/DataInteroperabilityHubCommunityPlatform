/**
 * Webhooks React Query Hooks
 * Real API; no mocks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type {
  WebhookCreateRequest,
  WebhookListFilters,
  WebhookUpdateRequest,
} from '../../../shared/types/webhooks';
import { webhookService } from '../services/webhookService';

const QUERY_KEYS = {
  list: (filters: WebhookListFilters) => ['webhooks', 'list', filters] as const,
  detail: (id: string) => ['webhooks', 'detail', id] as const,
  eventTypes: ['webhooks', 'event-types'] as const,
  deliveries: (webhookId: string, filters?: { page?: number; page_size?: number; status?: string }) =>
    ['webhooks', 'deliveries', webhookId, filters] as const,
};

export function useWebhooks(filters: WebhookListFilters = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.list(filters),
    queryFn: () => webhookService.list(filters),
  });
}

export function useWebhook(id: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id!),
    queryFn: () => webhookService.getById(id!),
    enabled: !!id,
  });
}

export function useWebhookEventTypes(odpsOnly = false) {
  return useQuery({
    queryKey: [...QUERY_KEYS.eventTypes, odpsOnly],
    queryFn: () => webhookService.getEventTypes(odpsOnly),
  });
}

export function useCreateWebhook() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: WebhookCreateRequest) => webhookService.create(data),
    successMessage: 'Webhook created',
    errorMessage: 'Failed to create webhook',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useUpdateWebhook() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: WebhookUpdateRequest }) =>
      webhookService.update(id, data),
    successMessage: 'Webhook updated',
    errorMessage: 'Failed to update webhook',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.detail(variables.id) });
    },
  });
}

export function useDeleteWebhook() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => webhookService.delete(id),
    successMessage: 'Webhook deleted',
    errorMessage: 'Failed to delete webhook',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useTestWebhook() {
  return useMutationWithNotification({
    mutationFn: (id: string) => webhookService.test(id),
    successMessage: 'Webhook test sent',
    errorMessage: 'Failed to test webhook',
  });
}

export function useWebhookDeliveries(
  webhookId: string,
  filters?: { page?: number; page_size?: number; status?: string }
) {
  return useQuery({
    queryKey: QUERY_KEYS.deliveries(webhookId, filters),
    queryFn: () => webhookService.getDeliveries(webhookId, filters),
    enabled: !!webhookId,
  });
}

export function useRetryWebhookDelivery(webhookId: string) {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (deliveryId: string) => webhookService.retryDelivery(deliveryId),
    successMessage: 'Delivery retry queued',
    errorMessage: 'Failed to retry delivery',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks', 'deliveries', webhookId] });
    },
  });
}
