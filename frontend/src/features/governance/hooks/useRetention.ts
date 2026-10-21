/**
 * Governance Retention React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type {
  RetentionPolicyCreateRequest,
  RetentionPolicyListFilters,
  RetentionPolicyUpdateRequest,
} from '../../../shared/types/governanceRetention';
import { governanceRetentionService } from '../services/governanceRetentionService';

export function useRetentionPolicies(filters: RetentionPolicyListFilters = {}) {
  return useQuery({
    queryKey: ['governance', 'retention-policies', 'list', filters],
    queryFn: () => governanceRetentionService.listPolicies(filters),
  });
}

export function useRetentionPolicy(id: string | null) {
  return useQuery({
    queryKey: ['governance', 'retention-policies', 'detail', id],
    queryFn: () => governanceRetentionService.getPolicy(id!),
    enabled: !!id,
  });
}

export function useCreateRetentionPolicy() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: RetentionPolicyCreateRequest) =>
      governanceRetentionService.createPolicy(data),
    successMessage: 'Retention policy created',
    errorMessage: 'Failed to create retention policy',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'retention-policies'] });
    },
  });
}

export function useUpdateRetentionPolicy() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: RetentionPolicyUpdateRequest) =>
      governanceRetentionService.updatePolicy(data),
    successMessage: 'Retention policy updated',
    errorMessage: 'Failed to update retention policy',
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'retention-policies'] });
      queryClient.invalidateQueries({
        queryKey: ['governance', 'retention-policies', 'detail', data.id],
      });
    },
  });
}

export function useDeleteRetentionPolicy() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => governanceRetentionService.deletePolicy(id),
    successMessage: 'Retention policy deleted',
    errorMessage: 'Failed to delete retention policy',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'retention-policies'] });
    },
  });
}

// ── Dashboard + quarterly report ─────────────────────────────

export function useRetentionDashboard(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['governance', 'retention', 'dashboard'],
    queryFn: () => governanceRetentionService.getDashboard(),
    enabled: options?.enabled !== false,
  });
}

export function useRetentionQuarterlyReport(period: string | null) {
  return useQuery({
    queryKey: ['governance', 'retention', 'quarterly-report', period],
    queryFn: () => governanceRetentionService.getQuarterlyReport(period!),
    enabled: !!period,
  });
}
