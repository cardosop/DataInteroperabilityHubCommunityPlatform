/**
 * Governance React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
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
  return useMutationWithNotification({
    mutationFn: (data: AccessRequestCreateRequest) => governanceService.create(data),
    successMessage: 'Access request created',
    errorMessage: 'Failed to create access request',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
    },
  });
}

export function useApproveAccessRequest() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, comments }: { id: string; comments?: string }) =>
      governanceService.approve(id, { comments }),
    successMessage: 'Access request approved',
    errorMessage: 'Failed to approve access request',
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
  return useMutationWithNotification({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      governanceService.reject(id, reason),
    successMessage: 'Access request rejected',
    errorMessage: 'Failed to reject access request',
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
      queryClient.invalidateQueries({
        queryKey: ['governance', 'access-requests', 'detail', data.id],
      });
    },
  });
}

export function useRevokeAccessRequest() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => governanceService.revoke(id),
    successMessage: 'Access revoked',
    errorMessage: 'Failed to revoke access',
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
      queryClient.invalidateQueries({
        queryKey: ['governance', 'access-requests', 'detail', data.id],
      });
    },
  });
}
