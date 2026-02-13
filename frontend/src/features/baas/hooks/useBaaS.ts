/**
 * BaaS React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { baasService } from '../services/baasService';
import type {
  APIKeyCreateRequest,
  APIKeyUpdateRequest,
  UsageFilters,
} from '../../../shared/types/baas';

export function useAPIKeys(filters: { tier?: string; active_only?: boolean } = {}) {
  return useQuery({
    queryKey: ['baas', 'api-keys', filters],
    queryFn: () => baasService.listAPIKeys(filters),
  });
}

export function useAPIKey(id: string | null) {
  return useQuery({
    queryKey: ['baas', 'api-keys', 'detail', id],
    queryFn: () => baasService.getAPIKey(id!),
    enabled: !!id,
  });
}

export function useCreateAPIKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: APIKeyCreateRequest) => baasService.createAPIKey(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys'] });
    },
  });
}

export function useUpdateAPIKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: APIKeyUpdateRequest }) =>
      baasService.updateAPIKey(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys'] });
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys', 'detail', variables.id] });
    },
  });
}

export function useRevokeAPIKey() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => baasService.revokeAPIKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys'] });
    },
  });
}

export function useUsageStats(filters: UsageFilters = {}) {
  return useQuery({
    queryKey: ['baas', 'usage', 'stats', filters],
    queryFn: () => baasService.getUsageStats(filters),
  });
}

export function useUsageByEndpoint(filters: UsageFilters = {}) {
  return useQuery({
    queryKey: ['baas', 'usage', 'by-endpoint', filters],
    queryFn: () => baasService.getUsageByEndpoint(filters),
  });
}

export function useUsageByTenant(filters: UsageFilters = {}) {
  return useQuery({
    queryKey: ['baas', 'usage', 'by-tenant', filters],
    queryFn: () => baasService.getUsageByTenant(filters),
  });
}
