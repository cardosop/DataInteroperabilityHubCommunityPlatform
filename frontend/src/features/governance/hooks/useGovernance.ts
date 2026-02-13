/**
 * Governance React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  AccessRequestCreateRequest,
  AccessRequestListFilters,
} from '../../../shared/types/governance';
import { governanceService } from '../services/governanceService';

export function useAccessRequests(filters: AccessRequestListFilters = {}) {
  return useQuery({
    queryKey: ['governance', 'access-requests', 'list', filters],
    queryFn: () => governanceService.list(filters),
  });
}

export function useAccessRequest(id: string | null) {
  return useQuery({
    queryKey: ['governance', 'access-requests', 'detail', id],
    queryFn: () => governanceService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateAccessRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AccessRequestCreateRequest) => governanceService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
    },
  });
}

export function useApproveAccessRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comments }: { id: string; comments?: string }) =>
      governanceService.approve(id, { comments }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
      queryClient.invalidateQueries({
        queryKey: ['governance', 'access-requests', 'detail', data.id],
      });
    },
  });
}

export function useRejectAccessRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      governanceService.reject(id, reason),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
      queryClient.invalidateQueries({
        queryKey: ['governance', 'access-requests', 'detail', data.id],
      });
    },
  });
}
