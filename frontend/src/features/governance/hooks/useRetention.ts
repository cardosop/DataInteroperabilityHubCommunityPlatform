/**
 * Governance Retention React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  return useMutation({
    mutationFn: (data: RetentionPolicyCreateRequest) =>
      governanceRetentionService.createPolicy(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'retention-policies'] });
    },
  });
}

export function useUpdateRetentionPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RetentionPolicyUpdateRequest) =>
      governanceRetentionService.updatePolicy(data),
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
  return useMutation({
    mutationFn: (id: string) => governanceRetentionService.deletePolicy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'retention-policies'] });
    },
  });
}
