/**
 * Governance React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../../../shared/components/Toast';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import type {
  AccessRequestCreateRequest,
  AccessRequestListFilters,
} from '../../../shared/types/governance';
import { governanceService } from '../services/governanceService';

export function useAccessRequests(
  filters: AccessRequestListFilters = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['governance', 'access-requests', 'list', filters],
    queryFn: () => governanceService.list(filters),
    enabled: options?.enabled !== false,
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

/**
 * Build a partial-failure-aware toast payload.
 * Backend returns HTTP 200 with `{succeeded, failed}` even when some rows
 * failed — so `useMutation.onSuccess` always fires, and we must inspect
 * the response to tell the user what actually happened.
 */
function summarizeBulkResult(
  data: { succeeded: string[]; failed: Array<{ id: string; error: string }> },
  verb: 'Approved' | 'Rejected',
): { message: string; tone: 'success' | 'info' | 'error' } {
  const s = data.succeeded.length;
  const f = data.failed.length;
  if (f === 0) {
    return {
      message: `${verb} ${s} request${s === 1 ? '' : 's'}.`,
      tone: 'success',
    };
  }
  if (s === 0) {
    const firstError = data.failed[0]?.error ?? 'unknown error';
    return {
      message: `Failed to ${verb.toLowerCase()} ${f} request${f === 1 ? '' : 's'}: ${firstError}`,
      tone: 'error',
    };
  }
  return {
    message: `${verb} ${s}; ${f} failed. First error: ${data.failed[0].error}`,
    tone: 'info',
  };
}

export function useBulkApproveAccessRequests() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ ids, comments }: { ids: string[]; comments?: string }) =>
      governanceService.bulkApprove(ids, comments),
    onSuccess: (data) => {
      const { message, tone } = summarizeBulkResult(data, 'Approved');
      toast[tone](message);
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
    },
    onError: () => {
      toast.error('Bulk approve request failed.');
    },
  });
}

export function useBulkRejectAccessRequests() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ ids, reason }: { ids: string[]; reason: string }) =>
      governanceService.bulkReject(ids, reason),
    onSuccess: (data) => {
      const { message, tone } = summarizeBulkResult(data, 'Rejected');
      toast[tone](message);
      queryClient.invalidateQueries({ queryKey: ['governance', 'access-requests'] });
    },
    onError: () => {
      toast.error('Bulk reject request failed.');
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

// ── Phase 272.1 — AccessRequestComment hooks ─────────────────

export function useAccessRequestComments(accessRequestId: string | null) {
  return useQuery({
    queryKey: ['governance', 'access-requests', 'comments', accessRequestId],
    queryFn: () => governanceService.listComments(accessRequestId!),
    enabled: !!accessRequestId,
  });
}

export function useCreateAccessRequestComment() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, body }: { id: string; body: string }) =>
      governanceService.createComment(id, body),
    successMessage: 'Comment added',
    errorMessage: 'Failed to add comment',
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['governance', 'access-requests', 'comments', variables.id],
      });
    },
  });
}
