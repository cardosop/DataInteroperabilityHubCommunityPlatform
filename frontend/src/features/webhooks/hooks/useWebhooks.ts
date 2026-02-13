/**
 * Webhooks React Query Hooks
 * Real API; no mocks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  return useMutation({
    mutationFn: (data: WebhookCreateRequest) => webhookService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useUpdateWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WebhookUpdateRequest }) =>
      webhookService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.detail(variables.id) });
    },
  });
}

export function useDeleteWebhook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => webhookService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
  });
}

export function useTestWebhook() {
  return useMutation({
    mutationFn: (id: string) => webhookService.test(id),
  });
}
