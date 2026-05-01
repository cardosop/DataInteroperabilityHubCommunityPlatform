/**
 * Phase 228.F3.15 — React Query hooks for the lineage-subscription
 * surface (REQ-LIN-F3-003).
 *
 * Exposes:
 *
 *   - `useLineageSubscriptions()`        — list mine
 *   - `useCreateLineageSubscription()`   — POST
 *   - `useUpdateLineageSubscription()`   — PATCH
 *   - `useDeleteLineageSubscription()`   — DELETE
 *
 * All hooks key off `['lineage', 'subscriptions']` so a single
 * invalidation refreshes every consumer (the settings page list,
 * the per-resource Subscribe button, the notification card link).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import { apiClient } from '../../../shared/api/client';

const BASE_PATH = '/lineage/subscriptions/';

export type LineageSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface LineageSubscription {
  id: string;
  user: string;
  source_contract: string | null;
  source_asset: string | null;
  severity_threshold: LineageSeverity;
  in_app: boolean;
  email: boolean;
  slack: boolean;
  created_at: string;
  last_dispatched_at: string | null;
}

export interface LineageSubscriptionListResponse {
  count: number | null;
  next_cursor: string | null;
  previous_cursor: string | null;
  page_size: number;
  results: LineageSubscription[];
}

export interface CreateLineageSubscriptionInput {
  source_contract?: string;
  source_asset?: string;
  severity_threshold?: LineageSeverity;
  in_app?: boolean;
  email?: boolean;
}

export interface UpdateLineageSubscriptionInput {
  severity_threshold?: LineageSeverity;
  in_app?: boolean;
  email?: boolean;
}

const subscriptionsKey = ['lineage', 'subscriptions'] as const;

export function useLineageSubscriptions(cursor?: string | null) {
  return useQuery({
    queryKey: [...subscriptionsKey, { cursor: cursor ?? null }],
    queryFn: async () => {
      const url = cursor ? `${BASE_PATH}?cursor=${encodeURIComponent(cursor)}` : BASE_PATH;
      const response = await apiClient.getClient().get<LineageSubscriptionListResponse>(url);
      return response.data;
    },
    staleTime: 30_000,
  });
}

export function useCreateLineageSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: CreateLineageSubscriptionInput) => {
      const response = await apiClient
        .getClient()
        .post<LineageSubscription>(BASE_PATH, input);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionsKey });
    },
  });
}

export function useUpdateLineageSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id, input,
    }: { id: string; input: UpdateLineageSubscriptionInput }) => {
      const response = await apiClient
        .getClient()
        .patch<LineageSubscription>(`${BASE_PATH}${id}/`, input);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionsKey });
    },
  });
}

export function useDeleteLineageSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.getClient().delete(`${BASE_PATH}${id}/`);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: subscriptionsKey });
    },
  });
}
