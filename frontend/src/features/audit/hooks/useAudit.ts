/**
 * Audit React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  AuditEventListFilters,
  AuditEventRetentionPolicyInput,
  ResourceType,
} from '../../../shared/types/audit';
import { useToast } from '../../../shared/components/Toast';
import { auditService } from '../services/auditService';

export function useAuditEvents(
  filters: AuditEventListFilters = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['audit', 'events', 'list', filters],
    queryFn: () => auditService.list(filters),
    enabled: options?.enabled !== false,
  });
}

export function useAuditEvent(id: string | null) {
  return useQuery({
    queryKey: ['audit', 'events', 'detail', id],
    queryFn: () => auditService.getById(id!),
    enabled: !!id,
  });
}

/**
 * Phase 224.3 — fetch the sanitized activity feed for a single resource.
 * Requires both ``resourceType`` and ``resourceId``; either missing → disabled.
 */
export function useResourceActivity(
  resourceType: ResourceType | null | undefined,
  resourceId: string | null | undefined,
  options?: { enabled?: boolean },
) {
  const enabled =
    options?.enabled !== false && !!resourceType && !!resourceId;
  return useQuery({
    queryKey: ['audit', 'resource-activity', resourceType, resourceId],
    queryFn: () => auditService.resourceActivity(resourceType!, resourceId!),
    enabled,
  });
}

// ── Phase 234.5 — Audit Event Retention Policy Hooks ───────────────────

export function useAuditEventRetentionPolicies(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['audit', 'retention-policies'],
    queryFn: () => auditService.listRetentionPolicies(),
    enabled: options?.enabled !== false,
  });
}

export function useCreateAuditEventRetentionPolicy() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (input: AuditEventRetentionPolicyInput) =>
      auditService.createRetentionPolicy(input),
    onSuccess: () => {
      toast.success('Retention policy created.');
      queryClient.invalidateQueries({ queryKey: ['audit', 'retention-policies'] });
    },
    onError: () => {
      toast.error('Failed to create retention policy.');
    },
  });
}

export function useUpdateAuditEventRetentionPolicy() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Partial<AuditEventRetentionPolicyInput> & { enabled?: boolean } }) =>
      auditService.updateRetentionPolicy(id, input),
    onSuccess: () => {
      toast.success('Retention policy updated.');
      queryClient.invalidateQueries({ queryKey: ['audit', 'retention-policies'] });
    },
    onError: () => {
      toast.error('Failed to update retention policy.');
    },
  });
}

export function useDeleteAuditEventRetentionPolicy() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: string) => auditService.deleteRetentionPolicy(id),
    onSuccess: () => {
      toast.success('Retention policy deleted.');
      queryClient.invalidateQueries({ queryKey: ['audit', 'retention-policies'] });
    },
    onError: () => {
      toast.error('Failed to delete retention policy.');
    },
  });
}
