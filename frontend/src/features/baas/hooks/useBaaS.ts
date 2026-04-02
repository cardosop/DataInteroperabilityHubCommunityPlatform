/**
 * BaaS React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { baasService } from '../services/baasService';
import type {
  APIKeyCreateRequest,
  APIKeyUpdateRequest,
  UsageFilters,
  BillingReportGenerateRequest,
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

  return useMutationWithNotification({
    mutationFn: (data: APIKeyCreateRequest) => baasService.createAPIKey(data),
    successMessage: 'API key created',
    errorMessage: 'Failed to create API key',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys'] });
    },
  });
}

export function useUpdateAPIKey() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: APIKeyUpdateRequest }) =>
      baasService.updateAPIKey(id, data),
    successMessage: 'API key updated',
    errorMessage: 'Failed to update API key',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys'] });
      queryClient.invalidateQueries({ queryKey: ['baas', 'api-keys', 'detail', variables.id] });
    },
  });
}

export function useRevokeAPIKey() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => baasService.revokeAPIKey(id),
    successMessage: 'API key revoked',
    errorMessage: 'Failed to revoke API key',
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

// --- Billing Reports (Phase 116C) ---

export function useBillingReports(filters: { customer_id?: string; status?: string } = {}) {
  return useQuery({
    queryKey: ['baas', 'billing-reports', filters],
    queryFn: () => baasService.listBillingReports(filters),
  });
}

export function useBillingReport(id: string | null) {
  return useQuery({
    queryKey: ['baas', 'billing-reports', 'detail', id],
    queryFn: () => baasService.getBillingReport(id!),
    enabled: !!id,
  });
}

export function useGenerateBillingReport() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: BillingReportGenerateRequest) => baasService.generateBillingReport(data),
    successMessage: 'Billing report generated',
    errorMessage: 'Failed to generate billing report',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'billing-reports'] });
    },
  });
}

export function useFinalizeBillingReport() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => baasService.finalizeBillingReport(id),
    successMessage: 'Report finalized',
    errorMessage: 'Failed to finalize report',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'billing-reports'] });
    },
  });
}

export function useSendBillingReport() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => baasService.sendBillingReport(id),
    successMessage: 'Report sent to customer',
    errorMessage: 'Failed to send report',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'billing-reports'] });
    },
  });
}

export function useVoidBillingReport() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => baasService.voidBillingReport(id, reason),
    successMessage: 'Report voided',
    errorMessage: 'Failed to void report',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['baas', 'billing-reports'] });
    },
  });
}
